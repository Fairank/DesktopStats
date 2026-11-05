"""Bounded read-only Windows network snapshots with psutil-compatible identity.

GAA keeps the original IP-adapter membership and FriendlyName order. Table2
provides the same 64-bit counters; the legacy table retains psutil 7.2.2's
CONNECTED/OPERATIONAL and admin-up rule. No address, DNS, service or adapter
configuration is changed. Construction performs no native calls.
"""

import ctypes as c
import os
import time
from collections import namedtuple

DISABLED = "DESKTOP_STATS_NETWORK_SNAPSHOT_DISABLED"
SNAPSHOT_API = "Windows network snapshot"
INVALID_DATA = 13
MAX_INTERFACES = 4096
MAX_BUFFER = 4 * 1024 * 1024
MAX_STRING = 256
GAA_FLAGS = 0xF
NetworkReading = namedtuple("NetworkReading", "bytes_recv bytes_sent isup identity", defaults=(None,))
U32, U64, U16 = c.c_uint32, c.c_uint64, c.c_uint16


class NativeUnavailable(Exception):
    """Initialization-only signal: platform/library/entry points are absent."""


class SnapshotError(OSError):
    def __init__(self, api, code):
        super().__init__(int(code), "Read-only network snapshot failed")
        self.api, self.winerror = api, int(code)


class Guid(c.Structure):
    _fields_ = [("a", U32), ("b", U16), ("d", U16), ("e", c.c_ubyte * 8)]


class InterfaceRow(c.Structure):
    _fields_ = [
        ("luid", U64), ("index", U32), ("guid", Guid),
        ("alias", U16 * 257), ("description", U16 * 257),
        ("physical_length", U32), ("physical", c.c_ubyte * 32), ("permanent", c.c_ubyte * 32),
        ("mtu", U32), ("type", U32), ("tunnel", U32), ("media_type", U32),
        ("physical_medium", U32), ("access", U32), ("direction", U32), ("flags", c.c_ubyte),
        ("oper", U32), ("admin", U32), ("media_connect", U32), ("network_guid", Guid),
        ("connection_type", U32), ("tx_link", U64), ("rx_link", U64),
        *[(name, U64) for name in (
            "in_octets", "in_ucast", "in_nucast", "in_discards", "in_errors", "in_unknown",
            "in_ucast_octets", "in_multicast_octets", "in_broadcast_octets", "out_octets",
            "out_ucast", "out_nucast", "out_discards", "out_errors", "out_ucast_octets",
            "out_multicast_octets", "out_broadcast_octets", "out_qlen")],
    ]


class InterfaceTable(c.Structure):
    _fields_ = [("count", U32), ("rows", InterfaceRow * 1)]


class LegacyRow(c.Structure):
    _fields_ = [
        ("name", U16 * 256),
        *[(name, U32) for name in ("index", "type", "mtu", "speed", "physical_length")],
        ("physical", c.c_ubyte * 8),
        *[(name, U32) for name in (
            "admin", "oper", "last_change", "in_octets", "in_ucast", "in_nucast",
            "in_discards", "in_errors", "in_unknown", "out_octets", "out_ucast", "out_nucast",
            "out_discards", "out_errors", "out_qlen", "description_length")],
        ("description", c.c_ubyte * 256),
    ]


class LegacyTable(c.Structure):
    _fields_ = [("count", U32), ("rows", LegacyRow * 1)]


class AdapterPrefix(c.Structure):
    # Pointer fields remain void*: c_wchar_p would dereference before validation.
    _fields_ = [
        ("length", U32), ("index", U32), ("next", c.c_void_p),
        ("adapter_name", c.c_void_p), ("first_unicast", c.c_void_p),
        ("first_anycast", c.c_void_p), ("first_multicast", c.c_void_p),
        ("first_dns_server", c.c_void_p), ("dns_suffix", c.c_void_p),
        ("description", c.c_void_p), ("friendly_name", c.c_void_p),
        ("physical", c.c_ubyte * 8), ("physical_length", U32), ("flags", U32),
        ("mtu", U32), ("type", U32), ("oper", U32), ("ipv6_index", U32),
        ("zones", U32 * 16), ("first_prefix", c.c_void_p),
        ("tx_link", U64), ("rx_link", U64), ("first_wins", c.c_void_p),
        ("first_gateway", c.c_void_p), ("ipv4_metric", U32), ("ipv6_metric", U32), ("luid", U64),
    ]


def _bad(api):
    raise SnapshotError(api, INVALID_DATA)


def _utf16(data, api):
    for offset in range(0, len(data) - 1, 2):
        if data[offset:offset + 2] == b"\0\0":
            # Match Windows Unicode code units without silently replacing names.
            return data[:offset].decode("utf-16-le", errors="surrogatepass")
    _bad(api)


class NativeNetworkApi:
    def __init__(self, *, library=None, loader=None):
        if c.sizeof(c.c_void_p) != 8 or c.sizeof(InterfaceRow) != 1352:
            raise NativeUnavailable()
        if library is None:
            if os.name != "nt":
                raise NativeUnavailable()
            try:
                library = (loader or c.WinDLL)("iphlpapi.dll", use_last_error=True)
            except AttributeError as error:
                raise NativeUnavailable() from error
            except OSError as error:
                if getattr(error, "winerror", None) in (126, 127):
                    raise NativeUnavailable() from error
                raise SnapshotError(SNAPSHOT_API, getattr(error, "winerror", None) or 13) from None
        try:
            self.gaa, self.table2 = library.GetAdaptersAddresses, library.GetIfTable2
            self.free, self.legacy = library.FreeMibTable, library.GetIfTable
        except AttributeError as error:
            raise NativeUnavailable() from error
        self.gaa.argtypes, self.gaa.restype = [U32, U32, c.c_void_p, c.c_void_p, c.POINTER(U32)], U32
        self.table2.argtypes, self.table2.restype = [c.POINTER(c.c_void_p)], U32
        self.free.argtypes, self.free.restype = [c.c_void_p], None
        self.legacy.argtypes, self.legacy.restype = [c.c_void_p, c.POINTER(U32), c.c_int], U32

    def adapters(self):
        api, size = "GetAdaptersAddresses", U32()
        code = self.gaa(0, GAA_FLAGS, None, None, c.byref(size))
        if code == 232:  # ERROR_NO_DATA: no IP adapters in this enumeration.
            return []
        if code != 111:
            raise SnapshotError(api, code or INVALID_DATA)
        for _attempt in range(3):
            if not c.sizeof(AdapterPrefix) <= size.value <= MAX_BUFFER:
                _bad(api)
            buffer = c.create_string_buffer(size.value)
            code = self.gaa(0, GAA_FLAGS, None, buffer, c.byref(size))
            if code == 111:
                continue
            if code:
                raise SnapshotError(api, code)
            if not c.sizeof(AdapterPrefix) <= size.value <= len(buffer):
                _bad(api)
            break
        else:
            raise SnapshotError(api, 111)
        start, end = c.addressof(buffer), c.addressof(buffer) + size.value

        def text(pointer):
            if not pointer or pointer % 2 or not start <= pointer < end:
                _bad(api)
            length = min((MAX_STRING + 1) * 2, end - pointer)
            return _utf16(c.string_at(pointer, length - length % 2), api)

        rows, seen, indices = [], set(), set()
        pointer = start
        while pointer:
            if (pointer in seen or len(rows) >= MAX_INTERFACES or pointer % 8
                    or not start <= pointer <= end - c.sizeof(AdapterPrefix)):
                _bad(api)
            seen.add(pointer)
            row = AdapterPrefix.from_address(pointer)
            if not c.sizeof(AdapterPrefix) <= row.length <= end - pointer:
                _bad(api)
            if not row.index or row.index in indices:
                _bad(api)
            indices.add(row.index)
            if not row.luid:
                _bad(api)
            rows.append((row.index, text(row.friendly_name), text(row.description), int(row.luid)))
            pointer = row.next
        return rows

    def counters(self):
        api, pointer, owned = "GetIfTable2", c.c_void_p(), False
        try:
            code = self.table2(c.byref(pointer))
            if code:
                raise SnapshotError(api, code)
            owned = True
            if not pointer or pointer.value % 8:
                _bad(api)
            count = U32.from_address(pointer.value).value
            if count > MAX_INTERFACES:
                _bad(api)
            rows = {}
            for index in range(count):
                row = InterfaceRow.from_address(pointer.value + InterfaceTable.rows.offset + index * c.sizeof(InterfaceRow))
                if not row.index or row.index in rows:
                    _bad(api)
                rows[row.index] = (
                    _utf16(bytes(row.alias), api), _utf16(bytes(row.description), api),
                    int(row.in_octets), int(row.out_octets), (int(row.luid), bytes(row.guid)),
                )
            return rows
        finally:
            if owned and pointer:
                self.free(pointer)

    def states(self):
        api, size = "GetIfTable", U32()
        code = self.legacy(None, c.byref(size), 0)
        if code != 122:
            raise SnapshotError(api, code or INVALID_DATA)
        for _attempt in range(3):
            if not LegacyTable.rows.offset <= size.value <= MAX_BUFFER:
                _bad(api)
            buffer = c.create_string_buffer(size.value)
            code = self.legacy(buffer, c.byref(size), 0)
            if code == 122:
                continue
            if code:
                raise SnapshotError(api, code)
            if not LegacyTable.rows.offset <= size.value <= len(buffer):
                _bad(api)
            break
        else:
            raise SnapshotError(api, 122)
        count = U32.from_buffer(buffer).value
        if count > MAX_INTERFACES or LegacyTable.rows.offset + count * c.sizeof(LegacyRow) > size.value:
            _bad(api)
        rows = {}
        for index in range(count):
            row = LegacyRow.from_buffer(buffer, LegacyTable.rows.offset + index * c.sizeof(LegacyRow))
            if not row.index or row.index in rows or row.description_length > 256:
                _bad(api)
            description = bytes(row.description[:row.description_length]).rstrip(b"\0")
            rows[row.index] = (description, row.oper in (4, 5) and row.admin == 1)
        return rows

    def read(self):
        adapters = self.adapters()
        if not adapters:
            return {}
        names, descriptions = set(), set()
        for _index, name, description, _luid in adapters:
            # psutil maps legacy descriptions to the first matching GAA name.
            # Ambiguous/non-ASCII narrowing retains that original path instead
            # of guessing which legacy row corresponds to which interface.
            if (not name or not description or name in names or description in descriptions
                    or not description.isascii()):
                return None
            names.add(name)
            descriptions.add(description)
        counters, states = self.counters(), self.states()
        legacy_descriptions = {}
        for description, _up in states.values():
            legacy_descriptions[description] = legacy_descriptions.get(description, 0) + 1
        result = {}
        for index, name, description, luid in adapters:
            if index not in counters or index not in states:
                _bad(SNAPSHOT_API)
            alias, current_description, received, sent, identity = counters[index]
            if luid != identity[0]:
                _bad(SNAPSHOT_API)
            legacy_description, up = states[index]
            encoded = description.encode("ascii")
            if (alias != name or current_description != description or legacy_description != encoded
                    or legacy_descriptions.get(encoded) != 1):
                return None
            result[name] = NetworkReading(received, sent, bool(up), identity)
        return result


class NetworkSnapshot:
    def __init__(self, *, api_factory=None, environ=None, clock=None):
        self._factory = api_factory or NativeNetworkApi
        self._environment = os.environ if environ is None else environ
        self._selected, self._fallback, self._api = False, False, None
        self._clock = clock or time.monotonic
        self._retry_at = 0.0

    def read(self):
        try:
            if not self._selected:
                if self._environment.get(DISABLED) == "1":
                    self._fallback = True
                else:
                    try:
                        self._api = self._factory()
                    except NativeUnavailable:
                        self._fallback = True
                self._selected = True
            if self._fallback:
                return None
            now = self._clock()
            if now < self._retry_at:
                return None
            result = self._api.read()
            if result is None:
                # Only the optimization backs off. Activity still queries the
                # original psutil sources on every requested sampling cycle.
                self._retry_at = now + 60.0
            return result
        except SnapshotError:
            raise
        except OSError as error:
            raise SnapshotError(SNAPSHOT_API, getattr(error, "winerror", None) or 13) from None
        except (ValueError, TypeError, UnicodeError, OverflowError, KeyError, AttributeError):
            _bad(SNAPSHOT_API)
