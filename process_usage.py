"""Transient, demand-only software resource rankings. Never saved or exported.

CPU is a percentage of the whole machine; memory is working-set bytes (including
shared pages). GPU engines are aggregated per software/engine, then the busiest
engine is selected, on the one explicitly identified DXGI adapter.
"""

import math
import sys
import threading
import time
from collections import defaultdict

import psutil

KINDS = frozenset(("cpu", "memory", "gpu", "vram"))
INTERVAL = 1.0


def resource_kind(metric):
    if metric.startswith("cpu_") and "fan" not in metric:
        return "cpu"
    if metric.startswith("vram_") or metric == "vram_gb":
        return "vram"
    if metric.startswith("gpu_") and "fan" not in metric:
        return "gpu"
    if metric.startswith(("ram_", "swap_")):
        return "memory"
    return ""


def valid(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def safe_error(error, api):
    result = dict(api=api, type=type(error).__name__)
    code = getattr(error, "code", None)
    if (getattr(error, "api", None) == "NtQuerySystemInformation"
            and isinstance(code, str) and len(code) == 10 and code.startswith("0x")
            and all(character in "0123456789abcdef" for character in code[2:])):
        result.update(api="NtQuerySystemInformation", code=code)
    for field in ("winerror", "errno"):
        if type(getattr(error, field, None)) is int:
            result[field] = getattr(error, field)
    return result


def empty_report(kind, state="warming_up", reason_code="", **extra):
    return dict(
        kind=kind,
        state=state,
        reason_code=reason_code,
        rows=[],
        unit="bytes" if kind in ("memory", "vram") else "%",
        denied_count=0,
        timestamp=None,
        **extra,
    )


class ProcessSource:
    """Fresh process identities; never request command lines, paths or accounts."""

    def snapshot(self, kinds):
        if sys.platform == 'win32':
            from process_snapshot import WindowsProcessSnapshot

            if getattr(self, '_native', None) is None:
                self._native = WindowsProcessSnapshot()
            snapshot = self._native.read()
            skipped = snapshot['skipped']
            return dict(rows=snapshot['rows'], denied={}, unidentified_count=skipped,
                        logical_cpus=psutil.cpu_count() if 'cpu' in kinds else None,
                        total_memory=psutil.virtual_memory().total if 'memory' in kinds else None)
        attrs = ["name", "create_time"]
        if "cpu" in kinds:
            attrs.append("cpu_times")
        if "memory" in kinds:
            attrs.append("memory_info")
        rows, denied = [], defaultdict(int)
        # Process(pid) is deliberately fresh. process_iter's cached create_time
        # can otherwise associate a recycled PID with the old software.
        for pid in psutil.pids():
            if pid == 0:
                continue
            try:
                info = psutil.Process(pid).as_dict(attrs=attrs, ad_value=None)
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                for kind in kinds:
                    denied[kind] += 1
                continue
            name, started = info.get("name"), info.get("create_time")
            if not isinstance(name, str) or not name.strip() or not valid(started):
                for kind in kinds:
                    denied[kind] += 1
                continue
            row = dict(pid=pid, started=started, name=name[:180])
            if "cpu" in kinds:
                cpu = info.get("cpu_times")
                if cpu is not None and valid(cpu.user) and valid(cpu.system):
                    row["cpu_seconds"] = cpu.user + cpu.system
                else:
                    denied["cpu"] += 1
            if "memory" in kinds:
                memory = info.get("memory_info")
                if memory is not None and valid(memory.rss):
                    row["memory_bytes"] = memory.rss
                else:
                    denied["memory"] += 1
            rows.append(row)
        return dict(
            rows=rows,
            denied=dict(denied),
            logical_cpus=psutil.cpu_count() if "cpu" in kinds else None,
            total_memory=psutil.virtual_memory().total if "memory" in kinds else None,
        )


class ProcessUsageSampler:
    """One worker owns all rate baselines and optional native GPU handles."""

    def __init__(self, *, source=None, gpu=None, clock=None, wall_clock=None):
        self.source = source if source is not None else ProcessSource()
        self.gpu = gpu
        self.clock, self.wall_clock = clock or time.monotonic, wall_clock or time.time
        self.previous, self.previous_at = {}, None
        self.closed = False

    def _gpu_read(self, kinds):
        if not kinds:
            if self.gpu is not None:
                self.gpu.close()
                self.gpu = None
            return {}
        if self.gpu is None:
            from process_gpu import GpuProcessCounters

            self.gpu = GpuProcessCounters()
        return self.gpu.read(kinds)

    def read(self, targets):
        if self.closed:
            return {key: empty_report(target["kind"], "closed") for key, target in targets.items()}
        kinds = {target["kind"] for target in targets.values()} & KINDS
        now = self.clock()
        elapsed = now - self.previous_at if self.previous_at is not None else None
        try:
            gpu = self._gpu_read(kinds & {"gpu", "vram"})
        except (OSError, ValueError, RuntimeError) as error:
            gpu = dict(
                errors={
                    kind: safe_error(error, "Windows GPU counters")
                    for kind in kinds & {"gpu", "vram"}
                }
            )
        try:
            snapshot = self.source.snapshot(kinds)
        except (OSError, psutil.Error, ValueError) as error:
            self.previous, self.previous_at = {}, None
            return {
                key: empty_report(
                    target["kind"],
                    "unavailable",
                    "query_failed",
                    error=safe_error(error, "psutil process snapshot"),
                )
                for key, target in targets.items()
            }
        processes = {}
        for row in snapshot.get("rows", ()):
            if (
                type(row.get("pid")) is int
                and row["pid"] > 0
                and valid(row.get("started"))
                and isinstance(row.get("name"), str)
                and row["name"].strip()
            ):
                processes[row["pid"]] = row
        timestamp = self.wall_clock()
        reports = {
            key: self._rank(target, processes, snapshot, gpu, elapsed, timestamp)
            for key, target in targets.items()
        }
        self.previous, self.previous_at = processes, now
        return reports

    def _rank(self, target, processes, snapshot, gpu, elapsed, timestamp):
        kind = target["kind"]
        if kind not in KINDS:
            return empty_report(kind, "unavailable", "not_attributable")
        denominator = 100
        denied = snapshot.get("denied", {}).get(kind, 0)
        totals, members, names = defaultdict(float), defaultdict(set), {}

        def add(process, value, engine=None):
            if not valid(value) or value <= 0:
                return
            name = process["name"].strip()[:180]
            key = name.casefold()
            names.setdefault(key, name)
            members[key].add(process["pid"])
            if engine is None:
                totals[key] += value
            else:
                totals[(key, engine)] += value

        def same_process(row):
            old = self.previous.get(row["pid"])
            return old if old and old["started"] == row["started"] else None

        if kind == "cpu":
            cpus = snapshot.get("logical_cpus")
            if elapsed is None or not 0.05 <= elapsed <= 30 or not valid(cpus) or cpus <= 0:
                return empty_report(kind, reason_code="rate_baseline")
            for row in processes.values():
                old = same_process(row)
                current, previous = row.get("cpu_seconds"), old.get("cpu_seconds") if old else None
                if valid(current) and valid(previous) and current >= previous:
                    add(row, (current - previous) / elapsed / cpus * 100)
        elif kind == "memory":
            denominator = snapshot.get("total_memory")
            for row in processes.values():
                add(row, row.get("memory_bytes"))
        else:
            if gpu.get("errors", {}).get(kind):
                return empty_report(kind, "unavailable", "query_failed", error=gpu["errors"][kind])
            adapters = [
                adapter
                for adapter in gpu.get("adapters", ())
                if adapter.get("name", "").strip().casefold()
                == target.get("hardware_name", "").strip().casefold()
            ]
            if any(adapter.get("pci_address") for adapter in adapters):
                # A reported non-PCI alias must not hide the matching physical
                # device. Missing/error metadata is still ambiguous, never guessed.
                adapters = [
                    adapter
                    for adapter in adapters
                    if "pci_address" not in adapter or adapter["pci_address"] is not None
                ]
            locations = {tuple(adapter.get("pci_address") or ()) for adapter in adapters}
            same_physical = (
                len(locations) == 1
                and len(next(iter(locations), ())) == 3
                and all(type(part) is int for part in next(iter(locations), ()))
                and next(iter(locations))[0] > 0
            )
            if (
                not adapters
                or len(adapters) != 1
                and not same_physical
                or any(not adapter.get("luid") for adapter in adapters)
            ):
                return empty_report(kind, "unavailable", "adapter_identity")
            if gpu.get("warming") or elapsed is None or not 0.05 <= elapsed <= 30:
                return empty_report(kind, reason_code="rate_baseline")
            adapter = adapters[0]
            luids = {adapter["luid"] for adapter in adapters}
            if kind == "vram":
                denominator = adapter.get("memory")
            for counter in gpu.get(kind, ()):
                process = processes.get(counter.get("pid"))
                if process is not None and same_process(process) and counter.get("luid") in luids:
                    engine = (counter.get("luid"), counter.get("engine")) if kind == "gpu" else None
                    add(process, counter.get("value"), engine)
            if kind == "gpu":
                engines = totals
                totals = defaultdict(float)
                for (key, _engine), value in engines.items():
                    totals[key] = max(totals[key], value)
        rows = []
        for key, value in totals.items():
            if kind in ("cpu", "gpu"):
                value = min(100.0, round(value, 4))
            fraction = (
                min(1.0, value / denominator) if valid(denominator) and denominator > 0 else 0.0
            )
            rows.append(
                dict(
                    name=names[key], value=value, fraction=fraction, process_count=len(members[key])
                )
            )
        rows.sort(key=lambda row: (-row["value"], row["name"].casefold(), row["name"]))
        unidentified = snapshot.get("unidentified_count", 0)
        state = "partial" if denied or unidentified else "ready" if rows else "idle"
        return dict(
            kind=kind,
            state=state,
            reason_code="",
            rows=rows[:5],
            denied_count=denied,
            unidentified_count=unidentified,
            unit="bytes" if kind in ("memory", "vram") else "%",
            timestamp=timestamp,
        )

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.previous, self.previous_at = {}, None
        if self.gpu is not None:
            self.gpu.close()
            self.gpu = None


class ProcessUsageMonitor:
    """Demand-only background snapshots at one-second start-to-start intervals.

    The callback receives a generation, so a closed/replaced detail card never
    receives a late sample from its predecessor. Unsupported resources never
    create a worker. Qt owns delivery back to the GUI thread, not this module.
    The initial CPU baseline gets one short follow-up; GPU rates need a second.
    """

    def __init__(self, callback, *, factory=ProcessUsageSampler):
        self.callback, self.factory = callback, factory
        self.condition = threading.Condition()
        self.targets, self.generation = {}, 0
        self.closed, self.thread = False, None

    def set_targets(self, targets):
        targets = {
            key: dict(target) for key, target in targets.items() if target.get("kind") in KINDS
        }
        with self.condition:
            if self.closed or targets == self.targets:
                return self.generation
            self.targets = targets
            self.generation += 1
            if targets and self.thread is None:
                self.thread = threading.Thread(
                    target=self._run, name="detail-process-usage", daemon=True
                )
                self.thread.start()
            self.condition.notify_all()
            return self.generation

    def _run(self):
        sampler, due, sampled_generation, last_finished = None, 0.0, -1, 0.0
        try:
            while True:
                retiring = None
                with self.condition:
                    while not self.closed:
                        if self.generation != sampled_generation:
                            due = max(time.monotonic(), last_finished + 0.05)
                        if not self.targets:
                            if sampler is not None:
                                retiring, sampler = sampler, None
                                due = 0.0
                                break
                            due = 0.0
                            self.condition.wait()
                        elif time.monotonic() < due:
                            self.condition.wait(due - time.monotonic())
                        else:
                            targets, generation = dict(self.targets), self.generation
                            break
                    stopped = self.closed
                if retiring is not None:
                    retiring.close()  # Never hold the GUI demand lock in native cleanup.
                if stopped:
                    return
                if retiring is not None:
                    continue
                started = time.monotonic()
                initial = sampler is None
                try:
                    if sampler is None:
                        sampler = self.factory()
                    results = sampler.read(targets)
                except Exception as error:
                    results = {
                        key: empty_report(
                            target["kind"],
                            "unavailable",
                            "query_failed",
                            error=safe_error(error, "process sampler"),
                        )
                        for key, target in targets.items()
                    }
                last_finished = time.monotonic()
                with self.condition:
                    current = not self.closed and generation == self.generation
                if current:
                    self.callback(generation, results)
                sampled_generation = generation
                gpu_demand = any(target["kind"] in ("gpu", "vram") for target in targets.values())
                period = max(INTERVAL, 1.05) if gpu_demand else INTERVAL
                if initial and any(value.get("state") == "warming_up" for value in results.values()):
                    if gpu_demand:
                        started = last_finished  # PDH's first collection follows lazy API setup.
                    else:
                        period = min(period, 0.25)
                # No query-duration drift and no bursts of catch-up queries.
                due = max(started + period, time.monotonic() + 0.05)
        finally:
            if sampler is not None:
                sampler.close()

    def close(self):
        with self.condition:
            self.closed = True
            self.targets = {}
            self.condition.notify_all()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.0)
