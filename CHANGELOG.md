# Changes

## 0.22.0-preview.1

- Add live per-logical-processor utilization to CPU details, with adaptive,
  scrollable cells and related frequency, temperature, package power and fan
  readings. Preserve valid zero, missing channels, independent sample age and
  recovery baselines; do not invent physical-core telemetry or per-core watts.
- Put visible adjust and remove buttons beside each menu-bar item. Give quiet
  action buttons clear boundaries, hover, focus and disabled states.
- Stage group membership and order locally with explicit Cancel and Confirm
  actions. Reject conflicting external edits, retain failed submissions for retry
  and include unconfirmed group edits in safe-exit protection.
- Add optional heat, flow, fan rotation and pulse decorations to menu-bar icons.
  Keep legacy configurations static by default, preserve independent device and
  paired-channel values, and stop motion for unavailable, zero, hidden or
  reduced-motion states. Decorative strength uses canonical units and does not
  indicate an alarm or an additional sensor reading.

## 0.21.0-preview.1

- Group up to four CPU or same-device GPU readings in one menu-bar item, while
  retaining existing display styles, units, device selection and the primary
  reading. Reorder, hover and overflow operate on the whole group; members retain
  independent missing-data states and their own trend units.
- Retain the PDH CPU-power observation time across cached reads so history does
  not count a cached value as a new hardware sample. Other providers keep their
  own timestamps when replacing that reading.
- Surface channel-level provider failures in diagnostics, including dictionary
  channel reports. Preserve allowlisted API names and numeric error codes in
  anonymous diagnostic exports without device identifiers or raw error strings.
- Keep keyboard-selected dropdown options in view, and give chart inspection
  priority over the settings window's Escape shortcut.
- Wait for the actual old process to exit before installation, recheck after
  staging, and leave an active dirty instance untouched. Clean up the server,
  owned PID marker and sampling resources after startup or shutdown failures.

## 0.20.0-preview.2

- Keep history read, write and clear failures independent. A temporary reader
  error must not postpone healthy writes; a successful read recovers its own
  state without hiding another operation's error.
- Reset source-time deduplication after a significant backwards system-clock
  correction, while preserving cached-sample filtering and bounded write cadence.
- Anchor history aggregation to a fixed time grid, so refreshing the window does
  not redistribute old observations into different means. Clip partial edge bins
  to the requested range and retain the point budget and exact summary values.
- Reusing the current scene no longer overwrites Previous layout or rearranges
  desktop windows. It can still discard pending workspace edits while retaining
  unrelated preference drafts. Restoring Previous layout shows the restored
  workspace's actual applied identity.
- Use one bounded 8 MiB UTF-8 budget for scene reads and writes. Eight legitimate
  complex workspaces remain readable; oversized replacements fail before changing
  the original file. Earlier valid scene files above 1 MiB can be read again.
- Dismiss an unconfirmed history deletion when leaving or hiding the page, and
  preserve an inspected chart observation across refreshes while its series,
  unit and real timestamp remain valid.
- Keep existing history visible after a failed clear when reading still succeeds,
  and contain reader rollback/close errors without losing their original API code.
- Add a six-image native-interface gallery to the repository README, with
  synthetic-data labels and reviewed source-only image assets.

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
