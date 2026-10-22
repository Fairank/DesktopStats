"""Pure multi-monitor placement: independent geometry, dock rows, no work-area edits."""

from magnet_layout import separated, settle
from native_layout import LayoutCapacityError, constrain, grid_plan, windows


def desktop_plan(config, screens, positions=None, rearrange=False):
    """Return fitted specs and positions keyed by window ID, all in logical DIP.

    Saved free positions stay on their monitor. Docked bars are centered at its
    top edge. Newly arranged windows avoid each other; this never reserves space
    from other applications or changes Windows' desktop work area.
    """
    if not config.get("visible", True):
        return [], {}
    if not screens:
        return windows(config), {}
    positions = positions or {}
    primary = next((s for s in screens if s.get("primary")), screens[0])
    indexed = {s["id"]: s for s in screens}
    buckets = {s["id"]: [] for s in screens}
    for spec in windows(config):
        selected = indexed.get(spec.get("screen_target"))
        # Reordering coordinates must not erase the monitor a user chose by
        # dragging a window there, even when no explicit screen is selected.
        point = positions.get(spec["id"])
        if selected is None and point and not spec.get("screen_target"):
            selected = next(
                (
                    s
                    for s in screens
                    if s["x"] <= point[0] + spec["width"] / 2 < s["x"] + s["width"]
                    and s["y"] <= point[1] + spec["height"] / 2 < s["y"] + s["height"]
                ),
                None,
            )
        selected = selected or primary
        saved_free = point is not None and not rearrange and spec.get("dock") != "top"
        # constrain reserves 36 DIP; saved free windows may use the complete
        # work area, while new/rearranged windows keep the existing inset.
        allowance = 36 if saved_free else 12
        fitted = constrain(spec, selected["width"] + allowance, selected["height"] + allowance)
        fitted["screen_id"] = selected["id"]
        buckets[selected["id"]].append(fitted)
    results, points = [], {}
    gap = config["magnet_gap"] if config.get("magnet_enabled") else 10
    for screen in screens:
        group = buckets[screen["id"]]
        occupied = []
        top = screen["y"] + 8
        for spec in [s for s in group if s.get("dock") == "top"]:
            x = screen["x"] + round((screen["width"] - spec["width"]) / 2)
            if top + spec["height"] > screen["y"] + screen["height"] - 8:
                raise LayoutCapacityError("Too many docked bars for this screen")
            points[spec["id"]] = [x, top]
            occupied.append((x, top, spec["width"], spec["height"]))
            top += spec["height"] + 8
            results.append(spec)
        floating = [s for s in group if s.get("dock") != "top"]
        area = (screen["x"] + 12, screen["y"] + 12, screen["width"] - 24, screen["height"] - 24)
        # Place saved windows first; ordinary manual overlaps remain intentional.
        floating.sort(key=lambda s: not (not rearrange and s["id"] in positions))
        fresh = [s for s in floating if rearrange or s["id"] not in positions]
        fresh_points = {}
        if fresh:
            # Apply the user's row/column/grid preference before collision
            # avoidance. Existing manually placed windows remain untouched.
            available_height = screen["y"] + screen["height"] - max(screen["y"], top)
            packed, locations = grid_plan(
                fresh, screen["width"], available_height, config.get("layout", "grid"), gap
            )
            fitted_by_id = {s["id"]: s for s in packed}
            floating = [fitted_by_id.get(s["id"], s) for s in floating]
            fresh_points = {
                s["id"]: (screen["x"] + p[0], max(screen["y"], top) + p[1])
                for s, p in zip(packed, locations)
            }
        for index, spec in enumerate(floating):
            old = positions.get(spec["id"]) if not rearrange else None
            if old is not None:
                # Dragging permits the full work area. Restoring a saved window
                # must use the same bounds rather than the fresh-layout inset.
                saved_area = (screen["x"], screen["y"], screen["width"], screen["height"])
                x = max(saved_area[0], min(round(old[0]), saved_area[0] + saved_area[2] - spec["width"]))
                y = max(saved_area[1], min(round(old[1]), saved_area[1] + saved_area[3] - spec["height"]))
                if config.get("magnet_enabled") and not separated(
                    (x, y, spec["width"], spec["height"]), occupied, gap
                ):
                    placed = settle(
                        (x, y, spec["width"], spec["height"]), occupied, [saved_area], gap=gap
                    )
                    if not placed.legal:
                        raise LayoutCapacityError("Saved windows cannot keep the selected spacing")
                    x, y = placed.x, placed.y
            else:
                x, y = fresh_points[spec["id"]]
                placed = settle((x, y, spec["width"], spec["height"]), occupied, [area], gap=gap)
                if not placed.legal:
                    raise LayoutCapacityError(
                        "Screen cannot fit all selected widgets at readable sizes"
                    )
                x, y = placed.x, placed.y
            occupied.append((x, y, spec["width"], spec["height"]))
            points[spec["id"]] = [x, y]
            results.append(spec)
    # Preserve instance order for z-order and context menus; dock geometry is set.
    order = {s["id"]: i for i, s in enumerate(windows(config))}
    results.sort(key=lambda s: order[s["id"]])
    return results, points
