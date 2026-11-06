"""Lazy, bounded, read-only enclosure identity from Windows SMBIOS.

Only the assembly view requests this snapshot. There is no WMI worker, driver,
poller or import-time I/O. Serial numbers, asset tags, UUIDs and
the raw firmware buffer are never returned, cached or persisted.

Contracts: Microsoft GetSystemFirmwareTable('RSMB'); DMTF DSP0134 3.9.0,
sections 7.2 (Type 1), 7.3 (Type 2) and 7.4 (Type 3), including
variable-position chassis SKU.
"""

import ctypes as c
from functools import lru_cache
import sys
import unicodedata

MAX_BYTES = 4 * 1024 * 1024
MAX_STRUCTURES = 4096
MAX_ENCLOSURES = 16
MAX_BASEBOARDS = 16
SOURCE_URLS = (
    "https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemfirmwaretable",
    "https://www.dmtf.org/sites/default/files/standards/documents/DSP0134_3.9.0.pdf",
)
_PLACEHOLDERS = frozenset(("", "unknown", "not specified", "none", "default string", "n/a",
                           "not applicable", "to be filled by o.e.m.", "to be filled by oem",
                           "system manufacturer", "system product name", "system version",
                           "system sku", "system family", "chassis manufacturer", "chassis version",
                           "sku", "systemproductname", "systemmanufacturer", "systemversion",
                           "systemsku", "systemfamily", "baseboard manufacturer", "baseboard product"))
_SYSTEM_FIELDS = ("manufacturer", "product", "version", "sku", "family")
_CHASSIS_FIELDS = ("manufacturer", "version", "sku", "type")
_BASEBOARD_FIELDS = ("manufacturer", "product", "board_type")


def _clean(raw):
    text = unicodedata.normalize("NFKC", raw[:512].decode("utf-8", errors="replace"))
    text = " ".join("".join(char for char in text if char.isprintable()).split())[:128]
    return "" if text.casefold() in _PLACEHOLDERS else text


def parse_smbios(raw):
    """Return whitelisted immutable fields, or None for malformed snapshots."""
    if not isinstance(raw, bytes) or not 8 <= len(raw) <= MAX_BYTES:
        return None
    if int.from_bytes(raw[4:8], "little") != len(raw) - 8:
        return None
    table, offset, structures, system, enclosures, baseboards = raw[8:], 0, 0, None, [], []
    while offset < len(table) and structures < MAX_STRUCTURES:
        if offset + 4 > len(table):
            return None
        kind, size = table[offset], table[offset + 1]
        if size < 4 or offset + size > len(table):
            return None
        end = table.find(b"\0\0", offset + size)
        if end < 0:
            return None
        record = table[offset:offset + size]
        strings = table[offset + size:end].split(b"\0")

        def string_at(position):
            index = record[position] if position < size else 0
            return _clean(strings[index - 1]) if 0 < index <= len(strings) else ""

        if kind == 1:
            if size < 8 or system is not None:
                return None
            system = tuple(string_at(position) for position in (4, 5, 6, 0x19, 0x1a))
        elif kind == 2:
            if size < 8:
                return None
            board_type = record[0x0d] if size > 0x0d else 0
            # A hosting motherboard or a legacy record with no type may aid
            # the assembly label. Other module boards are not substituted.
            if board_type in (0, 1, 10):
                baseboards.append((string_at(4), string_at(5), board_type))
                if len(baseboards) > MAX_BASEBOARDS:
                    return None
        elif kind == 3:
            if size < 9 or len(enclosures) >= MAX_ENCLOSURES:
                return None
            sku = ""
            if size >= 0x15:
                count, record_size = record[0x13], record[0x14]
                if count and record_size < 3:
                    return None
                sku_position = 0x15 + count * record_size
                if sku_position > size:
                    return None
                if sku_position < size:
                    sku = string_at(sku_position)
            enclosures.append((string_at(4), string_at(6), sku, record[5] & 0x7f))
        structures += 1
        offset = end + 2
        if kind == 127:
            return (system or ("",) * 5, tuple(enclosures), tuple(baseboards))
    if offset != len(table):
        return None
    return (system or ("",) * 5, tuple(enclosures), tuple(baseboards))


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
        return None


def snapshot():
    """Return detached public identity fields; subsequent calls perform no I/O."""
    data = _identity_once()
    if data is None:
        return dict(state="unavailable", source="Windows SMBIOS", system={}, enclosures=[], baseboards=[])
    system, enclosures, baseboards = data
    return dict(state="available", source="Windows SMBIOS", system=dict(zip(_SYSTEM_FIELDS, system)),
                enclosures=[dict(zip(_CHASSIS_FIELDS, row)) for row in enclosures],
                baseboards=[dict(zip(_BASEBOARD_FIELDS, row)) for row in baseboards])


def identify(info=None, manual_id=""):
    """Resolve an explicit case, exact enclosure firmware match, or unknown.

    Motherboard/system manufacturer alone never identifies a retail case.
    Manual selection changes the illustration only, not detected hardware.
    """
    from chassis_catalog import get_case, match_enclosure
    info = snapshot() if info is None else info
    if not isinstance(info, dict):
        info = dict(state="unavailable", system={}, enclosures=[])
    if manual_id:
        selected = get_case(manual_id)
        if selected is not None:
            return dict(state="manual", model_id=selected["id"], model=selected,
                        label=selected["label"], confidence="manual", reason="manual_illustration", firmware=info)
        return dict(state="unidentified", model_id="", model=None, label="机箱型号未确认",
                    confidence="unknown", reason="invalid_manual_selection", firmware=info)
    enclosures = info.get("enclosures", ())
    if not isinstance(enclosures, (list, tuple)):
        enclosures = ()
    matches = {row["id"]: row for enclosure in enclosures[:MAX_ENCLOSURES]
               if isinstance(enclosure, dict) for row in match_enclosure(enclosure)}
    if len(matches) == 1:
        selected = next(iter(matches.values()))
        return dict(state="automatic", model_id=selected["id"], model=selected,
                    label=selected["label"], confidence="firmware_exact", reason="exact_enclosure_identity", firmware=info)
    reason = "ambiguous_enclosure_identity" if len(matches) > 1 else (
        "firmware_unavailable" if info.get("state") == "unavailable" else "retail_model_not_reported")
    return dict(state="unidentified", model_id="", model=None, label="机箱型号未确认",
                confidence="unknown", reason=reason, firmware=info)
