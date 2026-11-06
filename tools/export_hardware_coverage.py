"""Export the reviewed public catalog without starting Qt, collectors or drivers.

Run directly to refresh docs/HARDWARE_COVERAGE.json, or use --check to verify
that the committed report matches the current offline metadata. No machine
identity, sensor reading, timestamp or locally detected hardware is consulted.
"""

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DESTINATION = ROOT / "docs" / "HARDWARE_COVERAGE.json"


def sources(*groups):
    """Keep only explicit, public HTTPS evidence, in reproducible order."""
    result = []
    for group in groups:
        for value in ((group,) if isinstance(group, str) else group or ()):
            parsed = urlsplit(value)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                    or parsed.password or "qa-private" in value):
                raise ValueError("Coverage evidence must be a public product URL")
            if value not in result:
                result.append(value)
    return result


def fact(value):
    unknown = value is None or value == "unknown"
    return {"status": "unknown" if unknown else "known", "value": None if unknown else value}


def not_applicable():
    return {"status": "not_applicable", "value": None}


def fan_coverage(row, appearance, evidence, *, inherited_from=None):
    """Count each reviewed front rotor; a known technology is not a blade count."""
    total = appearance.get("fan_count")
    front = appearance.get("visible_fan_count")
    if total == 0:
        return dict(status="not_applicable", physical_fans=fact(0), visible_front_fans=fact(0),
                    blades=None, front_blade_counts=[], geometry_status="not_applicable",
                    source_urls=evidence)
    common = row.get("blades")
    overrides = row.get("fans", ())
    if type(front) is not int or front < 0:
        front = len(overrides) if overrides else None
    counts = [overrides[index].get("blades", common) if index < len(overrides) else common
              for index in range(front or 0)]
    known = [type(count) is int and count > 0 for count in counts]
    if counts:
        status = "known" if all(known) else "partial" if any(known) else "unknown"
    else:
        status = "known" if type(common) is int and common > 0 else "unknown"
    result = dict(status=status, physical_fans=fact(total), visible_front_fans=fact(front),
                  blades=common, front_blade_counts=counts,
                  blade_pattern=fact(row.get('blade_pattern')),
                  front_hub_tones=[fact(overrides[index].get('hub_tone', row.get('hub_tone'))
                                       if index < len(overrides) else row.get('hub_tone'))
                                   for index in range(front or 0)],
                  confirmed_front_indices=[index for index, ready in enumerate(known) if ready],
                  unknown_front_indices=[index for index, ready in enumerate(known) if not ready],
                  technology=row.get("technology", "unknown"),
                  geometry_status=(appearance.get("fan_profile") or {}).get("artwork_status", "pending"),
                  source_urls=evidence)
    if inherited_from:
        result["inherited_from_model_id"] = inherited_from
    return result


def coverage(kind, series, row, appearance, fan_row, fan_sources, *, inherited_from=None):
    import hardware_board_details as boards

    result = dict(ports=not_applicable(), power=not_applicable(), pcb_length=not_applicable(),
                  pcb_internal_layout=not_applicable(), fans=not_applicable())
    if kind == "cpu":
        return result
    normal = boards.normalise(series, row, kind=kind)
    result["pcb_length"] = fact(normal.get("pcb_length"))
    result["pcb_internal_layout"] = dict(status="unverified", value=None)
    if kind == "memory":
        result["module"] = {key: fact(normal.get(key)) for key in
                            ("form", "generation", "pins", "heat_spreader", "diffuser",
                             "notch_ratio", "notch_width_ratio", "notch_depth_ratio")}
        standard = boards.MEMORY_KEYS.get((normal.get("generation"), normal.get("form")))
        result["module"]["mechanical_source_urls"] = sources(standard[1]) if standard else []
        result["module"]["mechanical_scope"] = "nominal_front_view_pcb_ratios_not_sku_tolerances"
        return result
    for field, raw_field in (("ports", "ports"), ("power", "power_connectors")):
        groups = normal[raw_field]
        result[field] = dict(status="unknown" if groups is None else
                             "confirmed_absent" if not groups else "known", groups=groups)
    result["power"]["connection_mode"] = (
        "alternative_positions" if normal["alternative_power"] else "positions_unverified")
    result["power"]["position"] = fact(normal["power_position"])
    result["dimensions_mm"] = {key: fact(value) for key, value in normal["dimensions_mm"].items()}
    result["host_interface"] = {key: fact(value) for key, value in normal["host_interface"].items()}
    result["fans"] = fan_coverage(fan_row, appearance, fan_sources, inherited_from=inherited_from)
    return result


def build_report():
    """Validate exact aliases and assemble metadata through existing public APIs."""
    import hardware_appearance as hardware
    import hardware_board_details as boards
    import hardware_fan_profiles as fans
    from hardware_series import SERIES_CATALOG
    from hardware_variant_art import ART
    import hardware_variants as variants
    import memory_appearance as memory

    if set(boards.PROFILES) != {row["id"] for row in SERIES_CATALOG}:
        raise ValueError("A GPU base series is missing its exterior coverage record")
    if set(boards.MEMORY_PROFILES) != {row["id"] for row in memory.SERIES_CATALOG}:
        raise ValueError("A memory base series is missing its exterior coverage record")
    catalog = {row[0]: row for row in hardware.CATALOG}
    memory_catalog = {row["id"]: row for row in memory.CATALOG}
    base_models = []
    series_rows = []

    def resolve(kind, alias):
        return (memory.appearance_for_memory(model=alias) if kind == "memory"
                else hardware.appearance_for(kind, alias))

    def verify(identity, kind, aliases, supported=True):
        if not aliases:
            raise ValueError("A coverage identity needs complete SKU aliases: " + identity)
        answers = [resolve(kind, alias) for alias in aliases]
        if supported:
            if any(answer.get("id") != identity or answer.get("confidence") != "model"
                   for answer in answers):
                raise ValueError("Exact alias no longer resolves to its documented identity: " + identity)
        elif any(answer.get("confidence") == "model" or answer.get("board_details") for answer in answers):
            raise ValueError("A pending version was mistaken for supported model art: " + identity)
        return answers[0]

    for kind, table in (("gpu", boards.PROFILES), ("memory", boards.MEMORY_PROFILES)):
        for series, raw in sorted(table.items()):
            version_ids = sorted(key for key, version in variants.RECORDS.items()
                                 if version["kind"] == kind and version["series_id"] == series)
            series_rows.append(dict(series_id=series, kind=kind, base_model_ids=list(raw["model_ids"]),
                                    reviewed_version_ids=version_ids, market_exhaustive=False,
                                    retail_version_scope=("reviewed_additions_only" if version_ids
                                                          else "representative_only")))
            for identity in raw["model_ids"]:
                entry = memory_catalog[identity] if kind == "memory" else catalog[identity]
                aliases = entry["aliases"] if kind == "memory" else entry[-1]
                label = entry["label"] if kind == "memory" else entry[4]
                appearance = verify(identity, kind, aliases)
                if appearance.get("board_details", {}).get("model_ids") != (identity,):
                    raise ValueError("Base exterior guard changed: " + identity)
                exterior_sources = sources(raw.get("source_urls"))
                fan = fans.PROFILES.get(series, {}) if kind == "gpu" else {}
                if fan and identity not in fan.get("model_ids", ()):
                    raise ValueError("Fan coverage borrowed another representative: " + identity)
                fan_sources = sources(fan.get("source_url", ()))
                base_models.append(dict(model_id=identity, kind=kind, series_id=series, label=label,
                                        aliases=list(aliases), match_status="validated_exact",
                                        source_urls=sources(exterior_sources, fan_sources),
                                        exterior_source_urls=exterior_sources,
                                        coverage=coverage(kind, series, raw, appearance, fan, fan_sources)))

    for identity, entry in sorted(catalog.items()):
        if entry[1] != "cpu":
            continue
        verify(identity, "cpu", entry[-1])
        base_models.append(dict(model_id=identity, kind="cpu", series_id=None, label=entry[4],
                                aliases=list(entry[-1]), match_status="validated_exact",
                                source_urls=sources(entry[8]),
                                coverage=coverage("cpu", "", {}, {}, {}, [])))

    base_by_id = {row["model_id"]: row for row in base_models}
    if len(base_by_id) != len(base_models):
        raise ValueError("Duplicate base-model coverage identity")
    version_rows = []
    for identity, version in sorted(variants.RECORDS.items()):
        kind, series, base = version["kind"], version["series_id"], version["base_model_id"]
        if identity in base_by_id or base not in base_by_id:
            raise ValueError("A version duplicates a base or lacks a documented base")
        supported = identity in variants.READY
        relation = version["visual_relation"]
        if supported and relation != "shared" and identity not in ART:
            raise ValueError("Different/unknown artwork requires an explicitly implemented recipe")
        appearance = verify(identity, kind, version["aliases"], supported)
        table = boards.PROFILES if kind == "gpu" else boards.MEMORY_PROFILES
        original = table[series]
        if base not in original["model_ids"]:
            raise ValueError("A version points at another series' representative")
        if supported:
            raw = variants.exterior_row(identity, original)
            if raw.get("model_ids") != (identity,):
                raise ValueError("A supported version lacks its own exterior guard")
            if not sources(version["source_urls"]):
                raise ValueError("Supported sharing needs the exact version's own published evidence")
            if identity in ART:
                # An independent cooler's own evidence supports its changed
                # rotor. Its old base's blade source is not evidence for it.
                fan = dict(raw.get("fan_profile", {}))
                fan.update(ART[identity].get("fan_profile", {}))
                exterior_sources = sources(version["source_urls"])
            else:
                if variants.base_identity(identity) != base:
                    raise ValueError("Shared exterior identity no longer points to its reviewed base")
                fan = copy.deepcopy(fans.PROFILES.get(series, {})) if kind == "gpu" else {}
                fan.update(raw.get("fan_profile", {}))
                exterior_sources = sources(original.get("source_urls"), version["source_urls"])
            fan_sources = sources(fan.get("source_url", ()), version["source_urls"]) if fan else []
            status = "supported_independent" if identity in ART else "supported_shared"
        else:
            # The inventory can hold its own verified facts. It cannot grant
            # any other field from an unimplemented or unverified base cooler.
            raw = dict(version.get("overrides", {}), model_ids=(identity,))
            fan = raw.get("fan_profile", {})
            appearance = dict(fan_count=None, visible_fan_count=raw.get("fan_count_front"))
            exterior_sources = sources(version["source_urls"])
            fan_sources = sources(version["source_urls"]) if fan else []
            status = "pending_" + relation
        version_rows.append(dict(model_id=identity, kind=kind, series_id=series,
                                 base_model_id=base, label=version["label"],
                                 aliases=list(version["aliases"]), visual_relation=relation,
                                 status=status, match_status="validated_exact" if supported else "not_enabled",
                                 recipe=ART.get(identity, {}).get("recipe"),
                                 sharing_scope="exterior_illustration_only",
                                 inherits_live_telemetry=False, inherits_chip_specifications=False,
                                 source_urls=sources(exterior_sources, fan_sources),
                                 exterior_source_urls=exterior_sources,
                                 coverage=coverage(kind, series, raw, appearance, fan, fan_sources,
                                                   inherited_from=base if supported and identity not in ART else None)))

    base_models.sort(key=lambda row: (row["kind"], row["model_id"]))
    gpu_base = [row for row in base_models if row["kind"] == "gpu"]
    summary = dict(base_series=len(series_rows),
                   base_series_by_kind=dict(sorted(Counter(row["kind"] for row in series_rows).items())),
                   base_models=len(base_models),
                   base_models_by_kind=dict(sorted(Counter(row["kind"] for row in base_models).items())),
                   reviewed_version_records=len(version_rows), supported_versions=len(variants.READY),
                   pending_versions=len(version_rows) - len(variants.READY),
                   version_statuses=dict(sorted(Counter(row["status"] for row in version_rows).items())),
                   runtime_supported_models=len(base_models) + len(variants.READY),
                   base_gpu_field_statuses={field: dict(sorted(Counter(
                       row["coverage"][field]["status"] for row in gpu_base).items()))
                       for field in ("ports", "power", "pcb_length", "pcb_internal_layout", "fans")})
    report = dict(schema_version=1, summary=summary,
                  scope=dict(market_exhaustive=False, machine_inventory=False, offline_only=True,
                           description="Curated exact representative products and reviewed additional SKUs; "
                                       "base-only families are not exhaustive retail-version inventories.",
                           sharing="Shared art confirms exterior appearance only. GPU/CPU temperatures, "
                                   "live RPM, load, power consumption and chip specifications are never inherited.",
                           unknowns="Unknown facts stay null. Empty external-power groups mean explicitly "
                                    "confirmed absence. Fan blade counts cover reviewed visible front rotors.",
                           pcb="Exterior evidence does not establish internal PCB circuit layouts.",
                           cpu="CPU identities are listed separately; GPU exterior and rotor fields do not apply."),
                metadata_modules=["hardware_appearance", "memory_appearance", "hardware_board_details",
                                  "hardware_fan_profiles", "hardware_variants", "hardware_variant_art"],
                base_series=series_rows, base_models=base_models, versions=version_rows)
    # Whitelist-shaped report rows above intentionally omit every dynamic
    # reading and chip-performance field, including for cross-chip shared art.
    forbidden = {"gpu_temp", "cpu_temp", "fan_rpm", "gpu_usage", "cpu_usage", "numeric_value",
                 "gpu_power", "cpu_power", "vram_total_gb", "core_clock", "recommended_psu"}
    pending = [report]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if forbidden & value.keys():
                raise ValueError("Exterior sharing must not publish inherited telemetry or chip specifications")
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the fixed report without rewriting it")
    args = parser.parse_args()
    report = build_report()
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.check:
        if not DESTINATION.is_file() or DESTINATION.read_text(encoding="utf-8") != encoded:
            raise SystemExit("Hardware coverage is stale; run tools/export_hardware_coverage.py")
    else:
        DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        DESTINATION.write_text(encoded, encoding="utf-8")
    print(json.dumps(dict(report="docs/HARDWARE_COVERAGE.json", checked=args.check,
                         **report["summary"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
