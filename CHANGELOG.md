# Changes

## 0.20.0-preview.1

- Add local history for supported CPU, memory, battery, power, fan, GPU and
  per-adapter network readings, with 10-minute, 1-hour and 24-hour views. Keep
  source timestamps, missing intervals, weighted means and real extrema; use
  straight segments and min/max ranges rather than smoothed decorative curves.
- Keep one-second buckets for an hour and minute rollups for seven days. Batch
  normal writes at most once per second and isolate history failures from live
  readings. Recording can be paused or cleared independently of layout drafts.
- Add previewable workspace scenes, named local layouts and recovery of the
  saved layout from before the last scene switch. Preserve unrelated preferences
  and roll back scene recovery state if saving the new configuration fails.
- Replace the source-text wall with actionable status cards, expandable API
  details, a fresh-reading check and an allowlisted diagnostic export without
  raw readings, device identifiers or local paths.
- Route supported top-bar details directly to the correct metric and device's
  history. Stop diagnostic timers during shutdown and reject reentrant settings
  requests after the owning host is replaced or closed.
- Preserve the approved Niangao artwork, existing display styles and native
  Windows material paths. Offscreen visual checks do not verify native blur.

## 0.19.0-preview.2

- Isolate Windows battery initialization and query failures from other readings;
  preserve API/error details, clear failed battery values, and retry after a delay.
- Enumerate NVIDIA devices independently. An inaccessible GPU 0 must not hide a
  healthy GPU 1 or silently turn it into the default device.
- Retain failed NVML cleanup ownership and retry before initializing a replacement;
  keep cleanup failures separate from the original reading error.
- Block new top-bar hosts and details as shutdown begins, including callbacks
  during preparation or cleanup. Retain failed cleanup resources for an explicit
  retry and do not reopen settings or menus after shutdown.
- Hide a closing top bar before clearing its material. A failed material request
  must not leave the old bar visible or release its ownership prematurely.

## 0.19.0-preview.1

- Isolate live sensor delivery from diagnostic-file export failures. Permission
  errors or a full disk must not stop healthy readings from reaching the interface.
- Preserve network/disk API failure reasons and numeric error codes instead of
  reporting every unavailable reading as a counter warm-up.
- Reuse unchanged HWiNFO registry exports after verifying access and their original
  FILETIME; do not repeatedly enumerate and parse every channel at fast sampling rates.
- Prepare a clean, allowlisted source snapshot with SHA-256 file integrity checks;
  omit old application releases, local profiles, logs and private QA records.
- Offer original new application versions under PolyForm Noncommercial 1.0.0;
  retain third-party and earlier MIT rights explicitly.
- Document a safe isolated test workflow and the limits of sensor and glass checks.

This is a development preview. An offscreen layout check is not proof of Windows
composition quality or universal hardware compatibility.
