"""Pure, actual-DIP assistance for the content editor; no UI or preference writes.

Rectangles are complete metric-ID maps of normalized content-area coordinates.
``body`` contains positive ``width``/``height`` in DIP, excluding widget padding
and title. Guides use DIP relative to that body, so only the view scales them.

Drag results contain ``rect, valid, guides, collisions, reason``. Batch results
contain ``positions, body, valid, changed, collisions, reason``; failed batches
return the original positions. Reasons are stable codes, not translated text.
All helpers copy their inputs. Controller owns commit, undo, persistence and the
outer-window 4096 x 2160 limit. Alt maps to ``bypass=True`` and disables only snap.
"""

from itertools import product
from math import ceil, floor, isfinite

from responsive_layout import CELL_WIDTH, GAP, ROW_HEIGHT

EPSILON = 1e-8
FIELDS = ("x", "y", "width", "height")


class LayoutAssistError(ValueError):
    """Malformed API input, distinct from a well-formed invalid drag candidate."""


def _number(value, name, *, positive=False, nonnegative=False):
    if type(value) not in (int, float) or not isfinite(value):
        raise LayoutAssistError(f"Invalid {name}")
    if positive and value <= 0 or nonnegative and value < 0:
        raise LayoutAssistError(f"Invalid {name}")
    return float(value)


def _body(body):
    if not isinstance(body, dict):
        raise LayoutAssistError("Invalid content body")
    return {
        key: _number(body.get(key), "body " + key, positive=True) for key in ("width", "height")
    }


def _rect(rect):
    if not isinstance(rect, dict):
        raise LayoutAssistError("Invalid metric rectangle")
    return {key: _number(rect.get(key), "rectangle " + key) for key in FIELDS}


def _positions(positions):
    if not isinstance(positions, dict) or not 1 <= len(positions) <= 6:
        raise LayoutAssistError("Choose one to six metrics")
    if any(not isinstance(key, str) or not key for key in positions):
        raise LayoutAssistError("Invalid metric ID")
    return {key: _rect(rect) for key, rect in positions.items()}


def _selection(positions, selection):
    ids = _ids(selection)
    if len(set(ids)) != len(ids) or any(key not in positions for key in ids):
        raise LayoutAssistError("Invalid metric selection")
    # Stable geometry and collision ordering follow content order, not click order.
    return tuple(key for key in positions if key in ids)


def _ids(values):
    if not isinstance(values, (tuple, list)) or any(
        not isinstance(key, str) or not key for key in values
    ):
        raise LayoutAssistError("Metric IDs must be a sequence of strings")
    return tuple(values)


def _pixels(rect, body):
    return {key: rect[key] * body["width" if key in ("x", "width") else "height"] for key in FIELDS}


def _normalized(rect, body):
    return {key: rect[key] / body["width" if key in ("x", "width") else "height"] for key in FIELDS}


def _overlap(a, b):
    return (
        min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]) > EPSILON
        and min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]) > EPSILON
    )


def _validation(positions, body):
    outside = any(
        r["x"] < -EPSILON
        or r["y"] < -EPSILON
        or r["width"] <= 0
        or r["height"] <= 0
        or r["x"] + r["width"] > 1 + EPSILON
        or r["y"] + r["height"] > 1 + EPSILON
        for r in positions.values()
    )
    unreadable = any(
        r["width"] * body["width"] < CELL_WIDTH - EPSILON
        or r["height"] * body["height"] < ROW_HEIGHT - EPSILON
        for r in positions.values()
    )
    keys = list(positions)
    colliding = set()
    for index, key in enumerate(keys):
        for other in keys[index + 1 :]:
            if _overlap(positions[key], positions[other]):
                colliding.update((key, other))
    collisions = [key for key in keys if key in colliding]
    reason = (
        "outside_content"
        if outside
        else "minimum_size"
        if unreadable
        else "overlap"
        if collisions
        else ""
    )
    return not reason, collisions, reason


def _batch(original, candidate, body, *, reason="", **extra):
    valid, collisions, detected = _validation(candidate, body)
    reason = reason or detected
    valid = valid and not reason
    result = {
        "positions": candidate if valid else original,
        "body": dict(body),
        "valid": valid,
        "changed": valid and candidate != original,
        "collisions": collisions,
        "reason": reason,
    }
    result.update(extra)
    return result


def _axis_candidates(axis, base, moving, peers, body, operation, threshold, grid):
    size_key = "width" if axis == "x" else "height"
    extent = body[size_key]
    start, length = moving[axis], moving[size_key]
    targets = [(0.0, "boundary", None, 0), (extent, "boundary", None, 0)]
    targets.append((extent / 2, "center", None, 1))
    for key, peer in peers.items():
        p = _pixels(peer, body)
        targets.extend(
            (
                (p[axis], "peer_edge", key, 2),
                (p[axis] + p[size_key], "peer_edge", key, 2),
                (p[axis] + p[size_key] / 2, "peer_center", key, 3),
            )
        )
    anchors = (
        (("end", length),)
        if operation == "resize"
        else (("start", 0.0), ("center", length / 2), ("end", length))
    )
    choices = []
    for anchor, offset in anchors:
        for target, kind, target_id, priority in targets:
            delta = target - (start + offset)
            if abs(delta) > threshold + EPSILON:
                continue
            value = base + delta
            guide = dict(axis=axis, position=target, kind=kind, target_id=target_id, anchor=anchor)
            choices.append((value, guide, (0, abs(delta), priority)))
    if grid:
        edge = start + length if operation == "resize" else start
        # Deterministic half-up grid rounding; Python round() uses even ties.
        target = floor(edge / grid + 0.5) * grid
        delta = target - edge
        if abs(delta) <= threshold + EPSILON:
            guide = dict(
                axis=axis,
                position=target,
                kind="grid",
                target_id=None,
                anchor="end" if operation == "resize" else "start",
            )
            choices.append((base + delta, guide, (1, abs(delta), 4)))
    choices.sort(key=lambda row: row[2])
    choices.append((base, None, (2, 0, 5)))
    return choices


def assist_rect(
    positions,
    metric_id,
    proposal,
    body,
    *,
    operation="move",
    enabled=True,
    bypass=False,
    threshold=6,
    grid=8,
):
    """Return a bounded drag/resize candidate and visible snap guides.

    Move keeps the original size; resize keeps the original top-left anchor.
    Resize stops at the actual 128 x 30 DIP readable floor. Semantic content/
    peer guides within threshold take precedence over the weak 8-DIP grid.
    Snapping never turns a legal unsnapped candidate into an overlap. Invalid
    overlap candidates remain visible and return stable *other* metric IDs;
    swapping an occupied slot is an explicit separate action, never a side effect.
    """
    positions, body = _positions(positions), _body(body)
    if metric_id not in positions or operation not in ("move", "resize"):
        raise LayoutAssistError("Invalid drag target or operation")
    threshold = _number(threshold, "snap threshold", nonnegative=True)
    grid = _number(grid, "grid interval", nonnegative=True)
    source = _pixels(positions[metric_id], body)
    requested = _pixels(_rect(proposal), body)
    candidate = dict(source)
    if operation == "move":
        for axis, size in (("x", "width"), ("y", "height")):
            candidate[axis] = max(0.0, min(body[size] - source[size], requested[axis]))
    else:
        for axis, size, minimum in (("x", "width", CELL_WIDTH), ("y", "height", ROW_HEIGHT)):
            candidate[size] = min(body[size] - source[axis], max(minimum, requested[size]))
    peers = {key: value for key, value in positions.items() if key != metric_id}

    def result(rect, guides=()):
        normalized = _normalized(rect, body)
        full = dict(positions, **{metric_id: normalized})
        valid, collisions, reason = _validation(full, body)
        return dict(
            rect=normalized,
            valid=valid,
            guides=list(guides),
            collisions=[key for key in collisions if key != metric_id],
            reason=reason,
        )

    unsnapped = result(candidate)
    if not enabled or bypass:
        return unsnapped
    axes = []
    for axis, size in (("x", "width"), ("y", "height")):
        field = axis if operation == "move" else size
        axes.append(
            _axis_candidates(
                axis, candidate[field], candidate, peers, body, operation, threshold, grid
            )
        )
    combinations = sorted(
        product(*axes),
        key=lambda pair: (
            -sum(row[2][0] == 0 for row in pair),
            sum(row[1] is None for row in pair),
            sum(row[2][1] for row in pair),
            tuple(row[2][2] for row in pair),
        ),
    )
    for x_choice, y_choice in combinations:
        rect = dict(candidate)
        x_field, y_field = ("x", "y") if operation == "move" else ("width", "height")
        rect[x_field], rect[y_field] = x_choice[0], y_choice[0]
        guides = [choice[1] for choice in (x_choice, y_choice) if choice[1] is not None]
        outcome = result(rect, guides)
        if outcome["valid"]:
            return outcome
    return unsnapped


def preset_layout(metric_ids, body, preset="auto", *, columns=None, gap=GAP):
    """Return all IDs in an automatic row/column/balanced grid.

    The returned body can expand to fit every reading. ``minimum`` contains the
    chosen topology's body floor; Controller adds its title/padding and checks
    outer limits. Auto balances rows after using width capacity; grid defaults
    to a balanced near-square count, or uses explicit columns from 1 through 6.
    """
    ids = _ids(metric_ids)
    _positions({key: dict(x=0, y=0, width=1, height=1) for key in ids})
    if len(set(ids)) != len(ids):
        raise LayoutAssistError("Choose distinct metrics")
    body = _body(body)
    gap = _number(gap, "layout gap", nonnegative=True)
    if preset not in ("auto", "horizontal", "vertical", "grid"):
        raise LayoutAssistError("Unsupported layout preset")
    if columns is not None and (type(columns) is not int or not 1 <= columns <= 6):
        raise LayoutAssistError("Invalid grid column count")
    count = len(ids)
    if preset == "horizontal":
        cols = count
    elif preset == "vertical":
        cols = 1
    elif preset == "grid":
        cols = min(count, columns if columns is not None else ceil(count**0.5))
    else:
        capacity = max(1, min(count, floor((body["width"] + gap) / (CELL_WIDTH + gap))))
        cols = ceil(count / ceil(count / capacity))
    rows = ceil(count / cols)
    minimum = dict(
        width=cols * CELL_WIDTH + (cols - 1) * gap, height=rows * ROW_HEIGHT + (rows - 1) * gap
    )
    effective = {key: max(body[key], minimum[key]) for key in body}
    w = (effective["width"] - (cols - 1) * gap) / cols
    h = (effective["height"] - (rows - 1) * gap) / rows
    positions = {
        key: _normalized(
            dict(x=index % cols * (w + gap), y=index // cols * (h + gap), width=w, height=h),
            effective,
        )
        for index, key in enumerate(ids)
    }
    return dict(
        positions=positions,
        body=effective,
        minimum=minimum,
        columns=cols,
        rows=rows,
        valid=True,
        changed=True,
        collisions=[],
        reason="",
        preset=preset,
    )


def align_layout(positions, body, selection, command, *, scope="selection"):
    """Align selected items to their envelope, or one/more items to content.

    Commands: left, center, right, top, middle, bottom. A single item always
    uses content scope. Illegal collisions return the whole original layout.
    """
    positions, body = _positions(positions), _body(body)
    ids = _selection(positions, selection)
    if command not in ("left", "center", "right", "top", "middle", "bottom"):
        raise LayoutAssistError("Unsupported alignment")
    if scope not in ("selection", "content"):
        raise LayoutAssistError("Unsupported alignment scope")
    if not ids:
        return _batch(positions, positions, body, reason="need_selection")
    horizontal = command in ("left", "center", "right")
    axis, size = ("x", "width") if horizontal else ("y", "height")
    if scope == "content" or len(ids) == 1:
        start, end = 0.0, 1.0
    else:
        start = min(positions[key][axis] for key in ids)
        end = max(positions[key][axis] + positions[key][size] for key in ids)
    fraction = 0 if command in ("left", "top") else 1 if command in ("right", "bottom") else 0.5
    target = start + (end - start) * fraction
    candidate = {key: dict(rect) for key, rect in positions.items()}
    for key in ids:
        candidate[key][axis] = target - candidate[key][size] * fraction
    return _batch(positions, candidate, body)


def distribute_layout(positions, body, selection, axis):
    """Equalize gaps while preserving the selected outer-edge envelope.

    At least three items are required. Negative gaps, boundary violations or
    collisions with unselected items reject the entire operation.
    """
    positions, body = _positions(positions), _body(body)
    ids = _selection(positions, selection)
    if axis not in ("x", "y", "horizontal", "vertical"):
        raise LayoutAssistError("Unsupported distribution axis")
    axis = "x" if axis in ("x", "horizontal") else "y"
    if len(ids) < 3:
        return _batch(positions, positions, body, reason="need_three")
    size = "width" if axis == "x" else "height"
    # Staggered items can overlap on this axis while remaining legal in 2-D.
    # Use the complete envelope, not centers of possibly nested rectangles.
    ordered = sorted(ids, key=lambda key: positions[key][axis])
    start = min(positions[key][axis] for key in ids)
    end = max(positions[key][axis] + positions[key][size] for key in ids)
    gap = (end - start - sum(positions[key][size] for key in ids)) / (len(ids) - 1)
    if gap < -EPSILON:
        return _batch(positions, positions, body, reason="insufficient_space")
    candidate = {key: dict(rect) for key, rect in positions.items()}
    cursor = start
    for key in ordered:
        candidate[key][axis] = cursor
        cursor += candidate[key][size] + max(0.0, gap)
    # Set the outer edges exactly to avoid drift on repeated actions.
    candidate[ordered[0]][axis] = start
    candidate[ordered[-1]][axis] = end - candidate[ordered[-1]][size]
    return _batch(positions, candidate, body)


def resize_layout(positions, old_body, new_body):
    """Preserve every normalized rectangle; expand a requested body if needed.

    This does not reflow a manual layout or rewrite a user's requested size.
    ``minimum`` and returned ``body`` allow Controller to show the effective
    readable size before one atomic outer-window resize transaction.
    """
    positions, old_body, new_body = _positions(positions), _body(old_body), _body(new_body)
    valid, _, reason = _validation(positions, old_body)
    if not valid:
        return _batch(positions, positions, old_body, reason=reason)
    minimum = dict(
        width=ceil(max(CELL_WIDTH / r["width"] for r in positions.values()) - EPSILON),
        height=ceil(max(ROW_HEIGHT / r["height"] for r in positions.values()) - EPSILON),
    )
    effective = {key: max(new_body[key], minimum[key]) for key in new_body}
    return _batch(
        positions,
        positions,
        effective,
        minimum=minimum,
        resized=effective != old_body,
        expanded=effective != new_body,
    )


def swap_layout(positions, body, first, second):
    """Explicitly exchange two complete slots; never push any other metric."""
    positions, body = _positions(positions), _body(body)
    if first not in positions or second not in positions:
        raise LayoutAssistError("Invalid swap target")
    candidate = {key: dict(rect) for key, rect in positions.items()}
    candidate[first], candidate[second] = candidate[second], candidate[first]
    return _batch(positions, candidate, body)


def append_layout(positions, old_body, new_ids, *, gap=GAP):
    """Append manual channels without moving any existing actual-DIP rectangle.

    ``new_ids`` contains only additional IDs, not the complete content list.
    Fill available 128 x 30 DIP slots in row-major order, with the requested
    gap from all neighbours. Remaining new items use balanced rows below the
    old body; only height expands. Return every old/new ID normalized against
    the effective body. Controller must check its outer-window limits before
    committing this complete map. Existing normalized fractions may change as
    the body grows; their visible positions and sizes in DIP stay unchanged.
    """
    positions, old_body = _positions(positions), _body(old_body)
    ids = _ids(new_ids)
    gap = _number(gap, "layout gap", nonnegative=True)
    if len(set(ids)) != len(ids) or any(key in positions for key in ids):
        raise LayoutAssistError("Append only distinct new metrics")
    if len(positions) + len(ids) > 6:
        raise LayoutAssistError("Choose one to six metrics")
    valid, _, reason = _validation(positions, old_body)
    if not valid:
        return _batch(positions, positions, old_body, reason=reason)
    pixels = {key: _pixels(value, old_body) for key, value in positions.items()}

    def fits(candidate):
        return all(
            candidate["x"] + candidate["width"] + gap <= other["x"] + EPSILON
            or other["x"] + other["width"] + gap <= candidate["x"] + EPSILON
            or candidate["y"] + candidate["height"] + gap <= other["y"] + EPSILON
            or other["y"] + other["height"] + gap <= candidate["y"] + EPSILON
            for other in pixels.values()
        )

    remaining = []
    for key in ids:
        xs = {0.0, old_body["width"] - CELL_WIDTH}
        ys = {0.0, old_body["height"] - ROW_HEIGHT}
        for item in pixels.values():
            xs.update((item["x"] - gap - CELL_WIDTH, item["x"] + item["width"] + gap))
            ys.update((item["y"] - gap - ROW_HEIGHT, item["y"] + item["height"] + gap))
        found = None
        for y in sorted(ys):
            if y < 0 or y + ROW_HEIGHT > old_body["height"] + EPSILON:
                continue
            for x in sorted(xs):
                if x < 0 or x + CELL_WIDTH > old_body["width"] + EPSILON:
                    continue
                candidate = dict(x=x, y=y, width=float(CELL_WIDTH), height=float(ROW_HEIGHT))
                if fits(candidate):
                    found = candidate
                    break
            if found:
                break
        if found:
            pixels[key] = found
        else:
            remaining.append(key)
    effective = dict(old_body)
    if remaining:
        count = len(remaining)
        capacity = max(1, min(count, floor((old_body["width"] + gap) / (CELL_WIDTH + gap))))
        columns = ceil(count / ceil(count / capacity))
        rows = ceil(count / columns)
        cell_width = (old_body["width"] - (columns - 1) * gap) / columns
        top = old_body["height"] + gap
        effective["height"] = top + rows * ROW_HEIGHT + (rows - 1) * gap
        for index, key in enumerate(remaining):
            pixels[key] = dict(
                x=index % columns * (cell_width + gap),
                y=top + index // columns * (ROW_HEIGHT + gap),
                width=cell_width,
                height=float(ROW_HEIGHT),
            )
    # Input content order remains stable even when one later ID fits a cavity
    # and an earlier ID needs an appended row.
    candidate = {key: _normalized(pixels[key], effective) for key in (*positions, *ids)}
    return _batch(positions, candidate, effective, added=list(ids), expanded=effective != old_body)
