# Desktop Stats sensor collector

This original MIT-licensed Windows console helper supplements Desktop Stats
with the actual device/sensor tree exposed by unmodified LibreHardwareMonitorLib
0.9.6. The main app consumes bounded local NDJSON; no browser or web server is
involved. The reviewed native ASUS, PDH and NVML providers remain independent.

Run `build.ps1` to compile locally using the existing Windows .NET Framework
compiler. It verifies every bundled library hash and creates
`runtime/DesktopStats.Collector.exe` plus its minimal nine-DLL dependency closure.
It never installs a runtime/SDK or downloads anything. `build.ps1 -SelfTest`
additionally runs a synthetic test; this does not construct/open `Computer`.

For source snapshots, first run `python tools/fetch_sensor_dependencies.py` from
the project root to obtain the exact verified libraries. You can then use
`python tools/build_collector.py --self-test` to compile with the same existing
Windows compiler, without changing PowerShell's execution policy. This entry
point also stages compilation before publishing its runtime and refuses to
replace a user-modified runtime. It does not install a compiler, driver or SDK.

The ordinary hardware path is separate: default collection continues until the
parent closes stdin or writes `stop` followed by a newline. Options are
`--interval 0.5..5` (default 1 second), `--once`, and optional `--duration SECONDS`
(greater than zero, at most one day). An OS-level collector supervisor must
enforce its own timeout when a hardware call blocks.

The group whitelist is fixed: GPU, storage and network. CPU, memory, battery,
motherboard, controllers, PSU and external power monitors are disabled. There
are no runtime commands to change this whitelist or control hardware. Fresh
upstream settings keep fan-control modes undefined. No third-party settings,
full reports, serial fields, GUI, elevation prompt, driver or installer is used.
The stock library's `Computer.Open` still allocates its CPUID/RDTSC executable
buffer even when CPU monitoring is off; no claim to the contrary is made.
The upstream 0.9.6 battery implementation can retain old values after status
query/tag failure, so the main app keeps its verified original Windows battery
provider instead: <https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/issues/2431>.

Schema 1 uses `provider`, `version`, UTC Unix-seconds `timestamp`, `hardware`
array and `sensors` array. Sensor IDs are complete library identifiers. Labels
are cleaned/bounded; IDs are never shortened. Values and observed session
minimum/maximum are finite numbers or null. Unknown units/types and control
targets are skipped. **Energy remains raw mWh** in this transport. The main
application explicitly converts mWh to Wh for display. Noise is not emitted
without a known calibrated source. Missing channels do not become zero.

See `third_party/librehardwaremonitor/0.9.6/NOTICE.md` and `manifest.json` for all
upstream source identities, license texts, release digest and DLL hashes. This
restricted implementation cannot create temperature, noise or input-power
sensors that the machine and its drivers do not expose.
