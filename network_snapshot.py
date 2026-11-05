"""Fresh Windows IP adapter membership and counters without per-interface calls.

GetAdaptersAddresses supplies the same friendly names/IP interface membership
as psutil. GetIfTable2 also includes filter interfaces, so membership must be
joined by LUID before publishing counters. Both native calls release the GIL.
ABI: Windows x64 IP_ADAPTER_ADDRESSES_LH and MIB_IF_ROW2, documented at
https://learn.microsoft.com/windows/win32/api/iptypes/ns-iptypes-ip_adapter_addresses_lh
https://learn.microsoft.com/windows/win32/api/netioapi/ns-netioapi-mib_if_row2
"""

import ctypes as c
import struct

POINTER_BYTES = c.sizeof(c.c_void_p)
INITIAL_BUFFER = 15 * 1024
MAX_BUFFER = 8 * 1024 * 1024
MAX_INTERFACES = 4096
MAX_ATTEMPTS = 3
ADAPTER_PREFIX = 232
ROW_BYTES = 1352
TABLE_OFFSET = 8
U32 = c.c_uint32


class NetworkSnapshotError(OSError):
    """Bounded API facts; never retain interface names or operating-system text."""

    def __init__(self, api, code=None, *, reason=None):
        super().__init__("Native network snapshot is unavailable")
        self.api = api
        if type(code) is int:
            self.winerror = code
        self.reason = reason or (None if type(code) is int else "InvalidNativeSnapshot")


def _symbol(api, name, arguments, result):
    try:
        callback = getattr(api, name)
        callback.argtypes, callback.restype = arguments, result
        return callback
    except (AttributeError, OSError) as error:
        raise NetworkSnapshotError(name, getattr(error, "winerror", None)) from None


class NativeNetworkSnapshot:
    def __init__(self, api=None):
        self._api = api
        self._buffer = None
        self._get_addresses = self._get_table = self._free_table = None

    def _bind(self):
        if POINTER_BYTES != 8:
            raise NetworkSnapshotError("GetIfTable2", reason="UnsupportedNativeABI")
        if self._get_addresses is not None:
            return
        try:
            api = self._api if self._api is not None else c.WinDLL("iphlpapi", use_last_error=True)
        except (OSError, AttributeError) as error:
            raise NetworkSnapshotError(
                "GetAdaptersAddresses", getattr(error, "winerror", None)
            ) from None
        addresses = _symbol(
            api, "GetAdaptersAddresses", [U32, U32, c.c_void_p, c.c_void_p, c.POINTER(U32)], U32
        )
        table = _symbol(api, "GetIfTable2", [c.POINTER(c.c_void_p)], U32)
        free = _symbol(api, "FreeMibTable", [c.c_void_p], None)
        self._api, self._get_addresses, self._get_table, self._free_table = (
            api,
            addresses,
            table,
            free,
        )

    def _adapters(self):
        if self._buffer is None:
            self._buffer = c.create_string_buffer(INITIAL_BUFFER)
        for _ in range(MAX_ATTEMPTS):
            capacity = c.sizeof(self._buffer)
            size = U32(capacity)
            # No address lists or DNS data are used by this provider.
            code = int(self._get_addresses(0, 0xF, None, self._buffer, c.byref(size)))
            if code == 232:  # ERROR_NO_DATA
                return {}
            if code == 111:  # ERROR_BUFFER_OVERFLOW
                if not capacity < size.value <= MAX_BUFFER:
                    raise NetworkSnapshotError("GetAdaptersAddresses", code)
                self._buffer = c.create_string_buffer(size.value)
                continue
            if code:
                raise NetworkSnapshotError("GetAdaptersAddresses", code)
            if not ADAPTER_PREFIX <= size.value <= capacity:
                raise NetworkSnapshotError("GetAdaptersAddresses")
            return self._adapter_rows(size.value)
        raise NetworkSnapshotError("GetAdaptersAddresses", 111)

    def _adapter_rows(self, length):
        start = c.addressof(self._buffer)
        end, current = start + length, start
        seen, aliases, result = set(), set(), {}
        while current:
            if (
                current % 8
                or current in seen
                or len(seen) >= MAX_INTERFACES
                or not start <= current <= end - ADAPTER_PREFIX
            ):
                raise NetworkSnapshotError("GetAdaptersAddresses")
            seen.add(current)
            raw = c.string_at(current, ADAPTER_PREFIX)
            record_length = struct.unpack_from("<I", raw)[0]
            if record_length < ADAPTER_PREFIX or current + record_length > end:
                raise NetworkSnapshotError("GetAdaptersAddresses")
            following = struct.unpack_from("<Q", raw, 8)[0]
            name = struct.unpack_from("<Q", raw, 72)[0]
            luid = struct.unpack_from("<Q", raw, 224)[0]
            if not luid or luid in result or name % 2 or not start <= name <= end - 2:
                raise NetworkSnapshotError("GetAdaptersAddresses")
            text = c.string_at(name, min(514, (end - name) // 2 * 2))
            terminator = next(
                (i for i in range(0, len(text), 2) if text[i : i + 2] == b"\0\0"), None
            )
            if terminator is None:
                raise NetworkSnapshotError("GetAdaptersAddresses")
            try:
                alias = text[:terminator].decode("utf-16-le", errors="strict")
            except UnicodeError:
                raise NetworkSnapshotError("GetAdaptersAddresses") from None
            if not alias or alias in aliases:
                raise NetworkSnapshotError("GetAdaptersAddresses")
            aliases.add(alias)
            result[luid] = alias
            current = following
        return result

    def _counters(self, adapters):
        pointer = c.c_void_p()
        try:
            code = int(self._get_table(c.byref(pointer)))
            if code:
                raise NetworkSnapshotError("GetIfTable2", code)
            address = pointer.value
            if not address or address < 4096 or address % 8:
                raise NetworkSnapshotError("GetIfTable2")
            count = c.cast(pointer, c.POINTER(U32)).contents.value
            if count > MAX_INTERFACES or address + TABLE_OFFSET + count * ROW_BYTES >= 2**64:
                raise NetworkSnapshotError("GetIfTable2")
            found, result = set(), {}
            for index in range(count):
                position = address + TABLE_OFFSET + index * ROW_BYTES
                luid = c.c_uint64.from_address(position).value
                if luid not in adapters:
                    continue
                if luid in found:
                    raise NetworkSnapshotError("GetIfTable2")
                found.add(luid)
                raw = c.string_at(position, ROW_BYTES)
                oper, admin = struct.unpack_from("<II", raw, 1156)
                rx_bytes, rx_unicast, rx_nonunicast, rx_drop, rx_error = struct.unpack_from(
                    "<5Q", raw, 1208
                )
                tx_bytes, tx_unicast, tx_nonunicast, tx_drop, tx_error = struct.unpack_from(
                    "<5Q", raw, 1280
                )
                result[adapters[luid]] = dict(
                    isup=oper == 1 and admin == 1,
                    identity=(luid, raw[12:28]),
                    bytes_sent=tx_bytes,
                    bytes_recv=rx_bytes,
                    packets_sent=tx_unicast + tx_nonunicast,
                    packets_recv=rx_unicast + rx_nonunicast,
                    errin=rx_error,
                    errout=tx_error,
                    dropin=rx_drop,
                    dropout=tx_drop,
                )
            if found != set(adapters):
                # A hot-unplug between the two tables must reset the rate
                # baseline; the next requested poll obtains a fresh snapshot.
                raise NetworkSnapshotError("GetIfTable2", reason="InterfaceInventoryChanged")
            # psutil publishes counters in GetAdaptersAddresses order. Keep
            # that order for equal-rate ties and the initial automatic choice.
            return {alias: result[alias] for alias in adapters.values()}
        finally:
            if pointer.value:
                self._free_table(pointer)

    def read(self):
        self._bind()
        adapters = self._adapters()
        return self._counters(adapters) if adapters else {}
