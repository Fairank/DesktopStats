# Changes

## 0.26.0-preview.2

- Stop treating the Shell's fullscreen ordering notification as a global veto
  on menu-bar details. A visible bar accepts a new click, hover or explicit
  details action even while either display retains a fullscreen observation.
  Continue applying the native AppBar ordering notifications independently.
- On a fresh entering transition, cancel only the affected host's older
  automatic hover. Defer its window cleanup outside the native callback and
  bind it to the exact panel and request generation. New pointer intent and
  pinned details survive delayed or duplicate notifications and other displays.
- Distinguish observed fullscreen ordering from detail admission in the local
  diagnostic snapshot. Preserve lifecycle, pause, HWND ownership, failed-cleanup
  and material preparation checks; do not infer which other app is fullscreen.
- Refine optional thermometer warmth, fan rotation and CPU/GPU core feedback
  for slightly clearer movement at menu-bar sizes. Keep real temperature column
  heights, independent power/heat layers and the existing off/reduced-motion
  and missing-data rules; add no animation timers, nodes or image assets.
- Retain unchanged device inventories between readings instead of deep-copying
  them on every sample. Stop hidden or minimized history pages querying the
  store and resume their selected view on exposure. Keep every raw sample and
  the configured detection interval.

## 0.26.0-preview.1

- Recover hidden or minimized menu-bar details on the next click or hover.
  A retained pinned record no longer counts as a visible window. Clear only
  the failed request's own unpublished state, so a creation failure can retry.
- Guard detail replacement and delayed placement by request generation as
  well as window identity. An earlier callback or exception cannot close or
  retarget the newer metric, even when both requests reuse the same window.
- Invalidate old fullscreen observations only after a verified replacement
  Shell process. Keep the guard for same-process display-scaling broadcasts
  and unavailable metadata; apply fresh registration-time notifications before
  showing the bar. No polling or user-window content inspection is added.
- Add a bounded, read-only detail diagnostic snapshot to local status replies.
  Distinguish fullscreen suppression, pending hover, and actual host/client
  visibility without collecting metric readings or creating a window.

## 0.25.0-preview.2

- Separate thermometer feedback from processor overload effects. Temperature
  symbols use a real temperature column and a local yellow/red thermal glow,
  without electrical discharge, including previously saved manual effects.
  Retain the accepted independent thermal/power arcs on CPU and GPU symbols.
- Keep temperature feedback device-scoped, unit-independent and optional;
  missing readings, disabled motion and reduced-motion settings retain the
  static thermometer. Clarify the temperature-specific settings description.

## 0.25.0-preview.1

- Correct optional icon effects that used the current reading only as an on/off
  gate. Drive local color, amplitude and rhythm from normalized live readings,
  with a short transition between samples. Retain an unambiguous static outline
  and the user's chosen effect, intensity and speed.
- Give heat, directional transfer, energy, fan and load feedback distinct local
  accents that remain visible at actual menu-bar and paired-readout sizes.
  Preserve zero, missing-data, hidden-window and reduced-motion stopping rules.
- Shape thermal feedback as intermittent yellow/red discharge at changing
  positions, with bright cores, natural branches and complete decay between
  individual bursts. Real power drives an independently timed blue discharge;
  the layers can coexist without changing the measured number or load area.
  Keep fan feedback to a clear rotating rotor and fixed hub.
- Add hardware-response profiles for processors, memory, transfer, batteries,
  fans, volumes and NVMe temperature. Independent real channels can coexist;
  missing load does not suppress a real thermal or power channel. Keep selected
  devices and canonical units isolated. Never infer memory heat or map SSD wear
  to current activity. Blend continuously across ten visual stages with
  increasing displacement, branch density and burst rate, without quantizing
  measured numbers.
- Keep these effects opt-in. Their visual response is not a calibrated fan RPM,
  electrical propagation simulation, temperature limit or alert severity.

## 0.24.0-preview.1

- Redesign optional menu-bar icon motion around each symbol's structure:
  separate transfer arrows, stationary fan hubs, local heat plumes and quiet
  inner-core feedback. Keep readable outlines and measured hit geometry stable.
  Use elapsed time for delayed ticks; retain default-off, strength, speed and
  reduced-motion controls without interpreting decorative rhythm as telemetry.
- Reorganize detail panels around current readings and real recent trends,
  followed by logical-processor load and related measurements. Use two-column
  groups, visible header actions and sample inspection with real gaps and units.
- Add an exact-width travelling drag preview and active-detail highlighting.
  Preserve source hit slots during dragging; release outside the strip or use
  the right mouse button to cancel without saving. Do not take keyboard focus
  from the application underneath the live bar.
- Keep automatic-network and system-volume history bound to the currently
  named device. Preserve idle zero, pre-device gaps, paired directions and unit
  conversions instead of splicing another device into the same chart.
- Exercise real preferences across fresh processes, section-only apply, live
  reordering, pending drafts and failed atomic writes. Keep the existing native
  Windows material backends; offscreen checks do not certify desktop blur.

## 0.23.0-preview.1

- Add three complete menu-bar treatments: Classic, Capsule and Instrument.
  Share the same chrome between the real bar and its live previews, including
  group boundaries, hover, pinned details, dragging and the overflow control.
  Choose treatments directly from miniature live bars; material inheritance,
  metric order, units, targets and existing display formats remain independent.
- Refine the ten metric formats with consistent numeric alignment, secondary
  units, paired directions and quantity-specific gauges. Preserve the exact
  measured widths and native hit regions at 28/32/40 logical pixels.
- Refine optional icon decorations and add continuous intensity and speed
  controls. Keep movement local, below 30 updates per second, and stop it when
  hidden, minimized, missing, inactive or reduced-motion is requested. Treat
  GPU fan percentages as fan motion in automatic mode, without implying RPM.
- Preserve default static legacy configurations and the existing native
  material path. Offscreen examples demonstrate layout, not Windows blur.
- Keep a history cursor chosen by the keyboard when pointer notifications
  arrive without movement; actual mouse motion resumes sample inspection.

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
