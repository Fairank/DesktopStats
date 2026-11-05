"""Windows per-process GPU/VRAM counters, opened only by the detail worker.

No administrator request, driver installation, WMI enumeration or helper
process. PDH names retain their LUID and physical engine, never an assumed
GPU index. DXGI interfaces and counter handles have bounded lifetimes.
"""

import ctypes as c
import math
import re
import time
import uuid
from ctypes import wintypes as w

PATHS = {
    "gpu": r"\GPU Engine(*)\Utilization Percentage",
    "vram": r"\GPU Process Memory(*)\Dedicated Usage",
}
_PREFIX = r"pid_(\d+)_luid_0x([0-9a-f]{1,8})_0x([0-9a-f]{1,8})_phys_(\d+)"
_ENGINE = re.compile(_PREFIX + r"_eng_(\d+)_engtype_([\w ]{1,64})", re.I)
_MEMORY = re.compile(_PREFIX, re.I)


class CounterError(OSError):
    def __init__(self, api, code):
        self.api, self.code = api, code & 0xFFFFFFFF
        super().__init__(f"{api}: 0x{self.code:08x}")

    def report(self):
        return dict(api=self.api, code=f"0x{self.code:08x}")


def parse_counter(instance, value, kind):
    if (
        not isinstance(instance, str)
        or type(value) not in (int, float)
        or not math.isfinite(value)
        or value < 0
    ):
        return None
    match = (_ENGINE if kind == "gpu" else _MEMORY).fullmatch(instance)
    if not match or int(match[1]) <= 0:
        return None
    row = dict(
        pid=int(match[1]), luid=f"{int(match[2], 16):08x}_{int(match[3], 16):08x}", value=value
    )
    if kind == "gpu":
        row["engine"] = f"{match[4]}_{match[5]}_{match[6]}"
    return row


class _ValueUnion(c.Union):
    _fields_ = [("long_value", c.c_int32), ("double_value", c.c_double), ("large_value", c.c_int64)]


class _Value(c.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("status", c.c_uint32), ("data", _ValueUnion)]


class _Item(c.Structure):
    _fields_ = [("name", c.c_void_p), ("value", _Value)]


class _Pdh:
    def __init__(self, lib=None):
        self.lib = lib if lib is not None else c.WinDLL("pdh", use_last_error=True)
        declarations = {
            "PdhOpenQueryW": [w.LPCWSTR, c.c_size_t, c.POINTER(c.c_void_p)],
            "PdhAddEnglishCounterW": [c.c_void_p, w.LPCWSTR, c.c_size_t, c.POINTER(c.c_void_p)],
            "PdhCollectQueryData": [c.c_void_p],
            "PdhGetFormattedCounterArrayW": [
                c.c_void_p,
                c.c_uint32,
                c.POINTER(c.c_uint32),
                c.POINTER(c.c_uint32),
                c.c_void_p,
            ],
            "PdhCloseQuery": [c.c_void_p],
        }
        for name, params in declarations.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = params, c.c_int32

    @staticmethod
    def check(status, api):
        if status:
            raise CounterError(api, status)

    def open(self, paths):
        query = c.c_void_p()
        self.check(self.lib.PdhOpenQueryW(None, 0, c.byref(query)), "PdhOpenQueryW")
        handles, errors = {}, {}
        try:
            for kind, path in paths.items():
                handle = c.c_void_p()
                status = self.lib.PdhAddEnglishCounterW(query, path, 0, c.byref(handle))
                if status:
                    errors[kind] = CounterError("PdhAddEnglishCounterW", status).report()
                else:
                    handles[kind] = handle
            if not handles:
                self.close(query)
                query = None
            return query, handles, errors
        except BaseException:
            if query:
                self.close(query)
            raise

    def collect(self, query):
        self.check(self.lib.PdhCollectQueryData(query), "PdhCollectQueryData")

    def values(self, handle):
        api = "PdhGetFormattedCounterArrayW"
        for _attempt in range(3):
            size, count = c.c_uint32(), c.c_uint32()
            status = self.lib.PdhGetFormattedCounterArrayW(
                handle, 0x8200, c.byref(size), c.byref(count), None
            )
            if not status and not count.value:
                return []
            if status & 0xFFFFFFFF != 0x800007D2:  # PDH_MORE_DATA
                self.check(status, api)
            if not c.sizeof(_Item) <= size.value <= 8 * 1024 * 1024:
                raise CounterError(api, 0xC0000BBC)  # Invalid returned buffer size.
            buffer = c.create_string_buffer(size.value)
            capacity = size.value
            status = self.lib.PdhGetFormattedCounterArrayW(
                handle, 0x8200, c.byref(size), c.byref(count), buffer
            )
            if status & 0xFFFFFFFF == 0x800007D2:
                continue  # Repeat the size query; do not trust a raced size.
            self.check(status, api)
            if count.value > 65536 or count.value * c.sizeof(_Item) > capacity:
                raise CounterError(api, 0xC0000BBC)
            items = c.cast(buffer, c.POINTER(_Item))
            start, end = c.addressof(buffer), c.addressof(buffer) + capacity
            result = []
            for index in range(count.value):
                item = items[index]
                if item.value.status not in (0, 1) or not item.name:
                    continue
                if not start <= item.name < end:
                    raise CounterError(api, 0xC0000BBC)
                bound = min(512, (end - item.name) // c.sizeof(c.c_wchar))
                text = c.wstring_at(item.name, bound)
                if "\0" not in text:
                    raise CounterError(api, 0xC0000BBC)
                result.append((text.split("\0", 1)[0], item.value.double_value))
            return result
        raise CounterError(api, 0x800007D2)

    def close(self, query):
        self.check(self.lib.PdhCloseQuery(query), "PdhCloseQuery")


class _Luid(c.Structure):
    _fields_ = [("low", c.c_uint32), ("high", c.c_int32)]


class _OpenAdapter(c.Structure):
    _fields_ = [("luid", _Luid), ("handle", c.c_uint32)]


class _AdapterQuery(c.Structure):
    _fields_ = [
        ("handle", c.c_uint32),
        ("kind", c.c_uint32),
        ("data", c.c_void_p),
        ("size", c.c_uint32),
    ]


def adapter_address(luid, *, lib=None):
    """Query the physical PCI location only (KMTQAITYPE_ADAPTERADDRESS=6)."""
    if not re.fullmatch(r"[0-9a-f]{8}_[0-9a-f]{8}", luid, re.I):
        raise ValueError("Invalid adapter LUID")
    library = lib if lib is not None else c.WinDLL("gdi32", use_last_error=True)
    for name, structure in (
        ("D3DKMTOpenAdapterFromLuid", _OpenAdapter),
        ("D3DKMTQueryAdapterInfo", _AdapterQuery),
        ("D3DKMTCloseAdapter", c.c_uint32),
    ):
        function = getattr(library, name)
        function.argtypes, function.restype = [c.POINTER(structure)], c.c_int32
    high, low = (int(part, 16) for part in luid.split("_"))
    request = _OpenAdapter(_Luid(low, c.c_int32(high).value), 0)
    status = library.D3DKMTOpenAdapterFromLuid(c.byref(request))
    if status or not request.handle:
        raise CounterError("D3DKMTOpenAdapterFromLuid", status or 0xC0000001)
    try:
        address = (c.c_uint32 * 3)()
        query = _AdapterQuery(request.handle, 6, c.addressof(address), c.sizeof(address))
        status = library.D3DKMTQueryAdapterInfo(c.byref(query))
        if status:
            raise CounterError("D3DKMTQueryAdapterInfo", status)
        if list(address) == [0xFFFFFFFF, 0xFFFF, 0xFFFF]:
            return None  # Windows explicitly returned no physical PCI location.
        if not 0 <= address[0] < 256 or address[1] > 31 or address[2] > 7:
            raise CounterError("D3DKMT adapter address validation", 0xC000000D)
        return list(address)
    finally:
        handle = c.c_uint32(request.handle)
        status = library.D3DKMTCloseAdapter(c.byref(handle))
        if status:
            raise CounterError("D3DKMTCloseAdapter", status)


class _Description(c.Structure):
    _fields_ = [
        ("name", c.c_wchar * 128),
        ("vendor", c.c_uint32),
        ("device", c.c_uint32),
        ("subsystem", c.c_uint32),
        ("revision", c.c_uint32),
        ("dedicated", c.c_size_t),
        ("system", c.c_size_t),
        ("shared", c.c_size_t),
        ("luid", _Luid),
        ("flags", c.c_uint32),
    ]


def _com_method(pointer, index, result, *params):
    table = c.cast(pointer, c.POINTER(c.POINTER(c.c_void_p))).contents
    return c.WINFUNCTYPE(result, c.c_void_p, *params)(table[index])


def dxgi_adapters(*, factory=None, method=None):
    method = method or _com_method
    if factory is None:
        library = c.WinDLL("dxgi", use_last_error=True)
        factory = library.CreateDXGIFactory1
        factory.argtypes = [c.c_void_p, c.POINTER(c.c_void_p)]
        factory.restype = c.c_int32
    iid = (c.c_ubyte * 16).from_buffer_copy(
        uuid.UUID("770aae78-f26f-4dba-a829-253c83d1b387").bytes_le
    )
    pointer = c.c_void_p()
    status = factory(c.byref(iid), c.byref(pointer))
    if status or not pointer:
        raise CounterError("CreateDXGIFactory1", status or 0x80004005)
    adapters = []
    try:
        enumerate_adapter = method(pointer, 12, c.c_int32, c.c_uint32, c.POINTER(c.c_void_p))
        for number in range(32):
            adapter = c.c_void_p()
            status = enumerate_adapter(pointer, number, c.byref(adapter))
            if status & 0xFFFFFFFF == 0x887A0002:  # DXGI_ERROR_NOT_FOUND
                return adapters
            if status or not adapter:
                raise CounterError("IDXGIFactory1.EnumAdapters1", status or 0x80004005)
            try:
                description = _Description()
                status = method(adapter, 10, c.c_int32, c.POINTER(_Description))(
                    adapter, c.byref(description)
                )
                if status:
                    raise CounterError("IDXGIAdapter1.GetDesc1", status)
                if not description.flags & 2:  # Exclude WARP/software adapters.
                    row = dict(
                        name=description.name.strip(),
                        luid=f"{description.luid.high & 0xFFFFFFFF:08x}_{description.luid.low:08x}",
                        memory=description.dedicated,
                        pci_vendor_id=description.vendor,
                        pci_device_id=description.device,
                        pci_subsystem_id=description.subsystem,
                        pci_revision=description.revision,
                    )
                    try:
                        row["pci_address"] = adapter_address(row["luid"])
                    except CounterError as error:
                        row["address_error"] = error.report()
                    except (OSError, ValueError, AttributeError) as error:
                        row["address_error"] = dict(
                            api="D3DKMT adapter address", type=type(error).__name__
                        )
                    adapters.append(row)
            finally:
                method(adapter, 2, c.c_uint32)(adapter)
        raise CounterError("DXGI adapter enumeration limit", 0x80004005)
    finally:
        method(pointer, 2, c.c_uint32)(pointer)


class GpuProcessCounters:
    def __init__(self, *, api=None, adapters=None, clock=None):
        self.api, self.adapter_provider = api, adapters or dxgi_adapters
        self.clock = clock or time.monotonic
        self.query, self.handles, self.errors = None, {}, {}
        self.kinds, self.adapters = set(), []
        self.retry_at = self.adapter_at = self.sample_at = float("-inf")
        self.closed = False

    def _release(self):
        query, self.query = self.query, None
        self.handles = {}
        self.sample_at = float("-inf")
        if query is not None:
            self.api.close(query)

    def read(self, kinds):
        kinds = set(kinds) & PATHS.keys()
        result = dict(gpu=[], vram=[], adapters=self.adapters, errors={}, warming=True)
        if self.closed:
            return result
        now = self.clock()
        try:
            if kinds != self.kinds:
                self._release()
                self.retry_at = float("-inf")
                self.errors = {}
                self.kinds = kinds
            if now < self.retry_at:
                result["errors"] = dict(self.errors)
                return result
            if now - self.adapter_at >= 30:
                self.adapters = self.adapter_provider()
                self.adapter_at = now
            result["adapters"] = self.adapters
            if self.query is None:
                if self.api is None:
                    self.api = _Pdh()
                self.query, self.handles, self.errors = self.api.open(
                    {kind: PATHS[kind] for kind in sorted(kinds)}
                )
                if self.query is None:
                    self.retry_at = now + 60
                    result["errors"] = dict(self.errors)
                    return result
            self.api.collect(self.query)
            result["warming"] = not 1 <= now - self.sample_at <= 30
            self.sample_at = now
            result["errors"] = dict(self.errors)
            if not result["warming"]:
                for kind, handle in self.handles.items():
                    try:
                        result[kind] = [
                            row
                            for name, value in self.api.values(handle)
                            if (row := parse_counter(name, value, kind)) is not None
                        ]
                    except CounterError as error:
                        result["errors"][kind] = error.report()
            return result
        except (OSError, ValueError, RuntimeError) as error:
            info = (
                error.report()
                if isinstance(error, CounterError)
                else dict(api="Windows GPU counters", type=type(error).__name__)
            )
            self.errors = {kind: info for kind in kinds}
            self.retry_at = now + 60
            try:
                self._release()
            except OSError:
                pass
            result.update(gpu=[], vram=[], errors=dict(self.errors), warming=True)
            return result

    def close(self):
        if not self.closed:
            self.closed = True
            self._release()
