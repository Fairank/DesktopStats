"""Read-only Windows activity providers and reset-safe monotonic rate sampling."""

import ctypes
import os
import time

import psutil

from network_snapshot import NetworkSnapshot


class _QueryFailure(RuntimeError):
    """Carry API facts without exception messages, filenames or adapter details."""

    def __init__(self, api, error):
        super().__init__(api)
        kind = next(
            (
                name
                for cls, name in (
                    (PermissionError, "PermissionError"),
                    (FileNotFoundError, "FileNotFoundError"),
                    (OSError, "OSError"),
                    (psutil.Error, "psutil.Error"),
                    (RuntimeError, "RuntimeError"),
                )
                if isinstance(error, cls)
            ),
            "QueryError",
        )
        self.facts = dict(api=api, reason=kind)
        for field in ("errno", "winerror"):
            value = getattr(error, field, None)
            if type(value) is int and -(2**31) <= value < 2**32:
                self.facts[field] = value


def _query(api, callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except (OSError, RuntimeError, psutil.Error) as error:
        raise _QueryFailure(api, error) from None


class Rates:
    def __init__(self):
        self.previous = {}

    def sample(self, counters, now):
        result = {}
        for key, values in counters.items():
            prior = self.previous.get(key)
            rates = [None] * len(values)
            if prior:
                elapsed = now - prior[0]
                if (
                    0.005 <= elapsed <= 30
                    and len(values) == len(prior[1])
                    and all(v >= p for v, p in zip(values, prior[1]))
                ):
                    rates = [(v - p) / elapsed for v, p in zip(values, prior[1])]
            result[key] = rates
        self.previous = {key: (now, values) for key, values in counters.items()}
        return result

    def clear(self):
        self.previous.clear()


class Activity:
    def __init__(self, *, network_reader=None):
        self.network_reader = NetworkSnapshot() if network_reader is None else network_reader
        self._network_identities = {}
        self._network_mode = None
        self.network_rates = Rates()
        self.disk_rates = Rates()
        self.volumes = []
        self.next_volumes = 0

    def network(self, now):
        try:
            snapshot = self.network_reader.read()
        except (OSError, RuntimeError, psutil.Error) as error:
            raise _QueryFailure(getattr(error, "api", "Windows network snapshot"), error) from None
        if snapshot is None:
            mode, identities = "psutil", {}
            counters = _query(
                "psutil.net_io_counters", psutil.net_io_counters, pernic=True, nowrap=False
            )
            statuses = _query("psutil.net_if_stats", psutil.net_if_stats)
            amounts = {
                name: (item.bytes_recv, item.bytes_sent)
                for name, item in counters.items()
                if name in statuses and statuses[name].isup and "loopback" not in name.lower()
            }
        else:
            mode = "native"
            try:
                amounts, identities = {}, {}
                for name, item in snapshot.items():
                    if (not isinstance(name, str) or type(item.isup) is not bool
                            or any(type(value) is not int or not 0 <= value < 2**64
                                   for value in (item.bytes_recv, item.bytes_sent))):
                        raise ValueError("Invalid network reading")
                    if item.isup and "loopback" not in name.lower():
                        amounts[name] = (item.bytes_recv, item.bytes_sent)
                        identity = getattr(item, "identity", None)
                        if identity is not None:
                            identities[name] = identity
            except (AttributeError, TypeError, ValueError, OverflowError):
                error = OSError(13, "Invalid network snapshot")
                error.winerror = 13
                raise _QueryFailure("Windows network snapshot", error) from None
        if self._network_mode is not None and self._network_mode != mode:
            self.network_rates.clear()
        for name, identity in identities.items():
            if name in self._network_identities and identity != self._network_identities[name]:
                self.network_rates.previous.pop(name, None)
        self._network_mode, self._network_identities = mode, identities
        rates = self.network_rates.sample(amounts, now)
        devices = {}
        for name, item in amounts.items():
            down, up = rates[name]
            devices[name] = dict(
                label=name,
                net_download=None if down is None else down / 1e6,
                net_upload=None if up is None else up / 1e6,
                net_received_gb=item[0] / 1e9,
                net_sent_gb=item[1] / 1e9,
            )
        # One active adapter avoids double-counting bridged/VPN traffic.
        chosen = max(devices, key=lambda k: sum(v or 0 for v in rates[k]), default=None)
        flat = {k: v for k, v in devices.get(chosen, {}).items() if k != "label"}
        return dict(networks=devices, network_active=chosen, **flat)

    def disk(self, now):
        counters = (
            _query("psutil.disk_io_counters", psutil.disk_io_counters, perdisk=True, nowrap=False)
            or {}
        )
        amounts = {name: (item.read_bytes, item.write_bytes) for name, item in counters.items()}
        rates = self.disk_rates.sample(amounts, now)
        disks = {}
        for name in amounts:
            read, write = rates[name]
            disks[name] = dict(
                label=name,
                disk_read=None if read is None else read / 1e6,
                disk_write=None if write is None else write / 1e6,
            )
        flat = {}
        for metric in ("disk_read", "disk_write"):
            values = [item[metric] for item in disks.values()]
            flat[metric] = sum(values) if values and all(v is not None for v in values) else None
        return dict(disks=disks, **flat)

    def storage(self, now):
        if now >= self.next_volumes:
            drive_type = _query("GetDriveTypeW", lambda: ctypes.windll.kernel32.GetDriveTypeW)
            drive_type.argtypes = [ctypes.c_wchar_p]
            self.volumes = [
                item.mountpoint
                for item in _query("psutil.disk_partitions", psutil.disk_partitions)
                if _query("GetDriveTypeW", drive_type, item.mountpoint) == 3
            ]  # Fixed local disks only.
            self.next_volumes = now + 30
        system = os.environ.get("SystemDrive", "C:") + "\\"
        volumes = {}
        errors = {}
        for path in self.volumes:
            volumes[path] = dict(label=path)
            try:
                item = _query("psutil.disk_usage", psutil.disk_usage, path)
                volumes[path].update(
                    disk_percent=item.percent,
                    disk_used_gb=item.used / 1024**3,
                    disk_free_gb=item.free / 1024**3,
                    disk_total_gb=item.total / 1024**3,
                )
            except _QueryFailure as error:
                errors[path] = error.facts
        flat = {k: v for k, v in volumes.get(system, {}).items() if k != "label"}
        state = (
            ("partial" if len(errors) < len(volumes) else "query_failed")
            if errors
            else ("ready" if volumes else "no_devices")
        )
        status = dict(state=state, requested=True)
        if errors:
            status["device_errors"] = errors
        return dict(
            volumes=volumes, volume_system=system, provider_status={"volumes": status}, **flat
        )

    def read(self, needed, inspecting=False):
        status = {}
        result = dict(provider_status=status)
        now = time.monotonic()
        for source, callback, rates in (
            ("network", self.network, self.network_rates),
            ("disk", self.disk, self.disk_rates),
        ):
            if source in needed or inspecting:
                try:
                    current = callback(now)
                    result.update(current)
                    devices = current["networks" if source == "network" else "disks"]
                    metrics = (
                        ("net_download", "net_upload")
                        if source == "network"
                        else ("disk_read", "disk_write")
                    )
                    state = (
                        "ready"
                        if all(
                            item.get(metric) is not None
                            for item in devices.values()
                            for metric in metrics
                        )
                        else "warming_up"
                    )
                    status[source] = dict(state=state if devices else "no_devices", requested=True)
                except _QueryFailure as error:
                    rates.clear()
                    status[source] = dict(state="query_failed", requested=True, error=error.facts)
                    result["networks" if source == "network" else "disks"] = {}
                    if source == "network":
                        result["network_active"] = None
                        self._network_identities, self._network_mode = {}, None
            else:
                rates.clear()
                if source == "network":
                    self._network_identities, self._network_mode = {}, None
                    status[source] = dict(state="not_requested", requested=False)
                    result.update(networks={}, network_active=None)
        # Throughput counters and volume capacity are independent demands.
        # The caller supplies "volumes" only for actual capacity metrics;
        # disk read/write widgets must not query every mounted drive's space.
        if "volumes" in needed or inspecting:
            try:
                current = self.storage(now)
                status.update(current.pop("provider_status"))
                result.update(current)
            except _QueryFailure as error:
                status["volumes"] = dict(state="query_failed", requested=True, error=error.facts)
                result["volumes"] = {}
        else:
            status["volumes"] = dict(state="not_requested", requested=False)
            # Keep only the bounded mount-point discovery cache internally.
            # No previous capacity values or errors belong to this new sample.
            result["volumes"] = {}
        return result
