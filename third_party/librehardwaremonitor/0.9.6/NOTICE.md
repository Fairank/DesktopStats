# Unmodified sensor libraries

These DLLs were extracted unchanged from LibreHardwareMonitor 0.9.6's official
Framework release. The published release-asset SHA-256 and each individual DLL
hash are recorded in `manifest.json`. They are dynamically used by the separate
Desktop Stats collector. No upstream GUI, plotting component, task scheduler,
setup executable, kernel driver, or driver installer is distributed here.

## MPL-2.0 components

`LICENSE-MPL-2.0.txt` applies to these unmodified assemblies. Their corresponding
source can be obtained without charge at the following immutable locations:

* LibreHardwareMonitorLib 0.9.6: copyright LibreHardwareMonitor contributors,
  with portions copyright Michael Möller and contributors.
  <https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/tree/3d331e3370efb858411f19511373eff65a218701>
* DiskInfoToolkit 1.1.2: copyright Florian K.
  <https://github.com/Blacktempel/DiskInfoToolkit/tree/25319eae5781e75bcf141e844ceab2afe94d40ea>
* RAMSPDToolkit-NDD 1.4.2: copyright Florian K.
  <https://github.com/Blacktempel/RAMSPDToolkit/tree/3b47b960e0830fef344624ad5e389675d5f0a1ce>
* BlackSharp.Core 1.0.7: copyright Florian K.
  <https://github.com/Blacktempel/BlackSharp/tree/c70b735c6cec123ee8a046ac4a0bc6c606f52cf0>

The original library files have not been modified. If you distribute changes to
covered source files, retain notices and meet the MPL's source availability
requirements. The main Desktop Stats application and original collector source
have their own license; they do not replace these licenses.

## Embedded PawnIO modules

LibreHardwareMonitorLib contains signed PawnIO module resources, copyright
namazso. Their LGPL-2.1 text is retained in
`LICENSE-PawnIO-Modules-LGPL-2.1.txt`. All twelve module resources in the pinned
LHM source match the official PawnIO.Modules **0.2.2** release binary hashes.
The upstream resource README's old 0.1.6 label is not used as provenance.
Corresponding source, build information and the upstream notices are available
at <https://github.com/namazso/PawnIO.Modules/tree/e12a858d952461ee2e919897cacbff7f905fe370>.

The restricted collector does not enable any group that loads these modules.
The PawnIO kernel driver, user-mode PawnIOLib and installer are not included.
No permission to install them is inferred by this notice.

## HidSharp 2.6.4

Copyright 2010–2025 James F. Bellinger. Apache License 2.0; the author's complete
copyright and license text are retained in `LICENSE-HidSharp-Apache-2.0.txt`.
The exact official package is <https://www.nuget.org/packages/HidSharp/2.6.4>.

## Microsoft support assemblies

System.Memory 4.6.3, System.Buffers 4.6.1, System.Numerics.Vectors 4.6.1 and
System.Runtime.CompilerServices.Unsafe 6.1.2 are copyright Microsoft Corporation
and contributors and licensed under MIT. See `LICENSE-Microsoft-MIT.txt` and the
individual immutable source/package identities in `manifest.json`.

Ordinary .NET Framework system assemblies are supplied by Windows/the installed
Framework and are not copied into this bundle.
