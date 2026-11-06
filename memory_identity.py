"""One-shot, read-only memory identity; never SPD/SMBus, WMI or a poller.

Only a modern top-bar RAM glyph requests it. Windows supplies a bounded SMBIOS
snapshot (one size query and one data read), cached including failure. Type 17
manufacturer, part number and form factor are the only retained fields; serial
numbers, asset tags and the raw firmware buffer are never returned or written.

Contracts: Microsoft GetSystemFirmwareTable('RSMB'), DMTF DSP0134 3.9 section
7.18 (Type 17). Source references are in HARDWARE-APPEARANCE.md.
"""

import ctypes as c
import sys
from functools import lru_cache

MAX_BYTES = 4 * 1024 * 1024
MAX_DEVICES = 64


def requested(config):
    bar = config.get("top_bar", {})
    return bool(bar.get("enabled") is True
                and bar.get("hardware_icon_style") in ("outline", "solid", "miniature", "soft", "cartoon")
                and any(isinstance(item, dict) and str(item.get("metric", "")).startswith("ram_")
                        and not item.get("prefs", {}).get("sensor_bindings")
                        for item in bar.get("items", ())))


def _clean(raw):
    text = raw[:256].decode("utf-8", errors="replace").strip()
    text = "".join(char for char in text if char.isprintable())[:128]
    return "" if text.casefold() in ("unknown", "not specified", "none", "default string", "n/a") else text


def parse_smbios(raw):
    """Parse only populated memory devices; malformed snapshots yield no data."""
    if not isinstance(raw, bytes) or not 8 <= len(raw) <= MAX_BYTES:
        return ()
    length = int.from_bytes(raw[4:8], "little")
    if length != len(raw) - 8:
        return ()
    table, offset, structures, rows = raw[8:], 0, 0, []
    while offset < len(table) and structures < 4096:
        if offset + 4 > len(table):
            return ()
        kind, size = table[offset], table[offset + 1]
        if size < 4 or offset + size > len(table):
            return ()
        end = table.find(b"\0\0", offset + size)
        if end < 0:
            return ()
        if kind == 17 and size >= 0x0f:
            record = table[offset:offset + size]
            populated = int.from_bytes(record[0x0c:0x0e], "little") != 0
            if populated:
                strings = table[offset + size:end].split(b"\0")
                def string_at(position):
                    index = record[position] if position < size else 0
                    return _clean(strings[index - 1]) if 0 < index <= len(strings) else ""
                rows.append((string_at(0x17), string_at(0x1a),
                             {0x09: "dimm", 0x0d: "sodimm", 0x12: "cudimm", 0x13: "csodimm"}.get(record[0x0e], "unknown")))
                if len(rows) > MAX_DEVICES:
                    return ()
        structures += 1
        offset = end + 2
        if kind == 127:
            return tuple(rows)
    return tuple(rows) if offset == len(table) else ()


def _read_raw_table():
    if sys.platform != "win32":
        return b""
    query = c.WinDLL("kernel32", use_last_error=True).GetSystemFirmwareTable
    query.argtypes = [c.c_uint32, c.c_uint32, c.c_void_p, c.c_uint32]
    query.restype = c.c_uint32
    provider = int.from_bytes(b"RSMB", "big")
    size = query(provider, 0, None, 0)
    if not 8 <= size <= MAX_BYTES:
        return b""
    buffer = c.create_string_buffer(size)
    if query(provider, 0, buffer, size) != size:
        return b""
    return buffer.raw


@lru_cache(maxsize=1)
def _identity_once():
    try:
        return parse_smbios(_read_raw_table())
    except (OSError, AttributeError, ValueError, OverflowError):
        return ()


def modules():
    """Return detached public identity fields; subsequent calls do no I/O."""
    return [dict(manufacturer=maker, part_number=part, form_factor=form)
            for maker, part, form in _identity_once()]
