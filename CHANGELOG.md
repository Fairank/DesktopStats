# Changes

## 0.32.0-preview.1

- Remove the visible desktop-widget corner grip while preserving corner resize
  behavior. Give unchanged automatic three-metric defaults a primary/supporting
  hierarchy; retain customized ordering, manual layouts and existing templates.
- Add an optional, rotatable OpenGL assembly window with exploded and component
  views. Convert the existing 178-entry hardware catalog into original schematic
  meshes, retaining reviewed shells, fan geometry, CPU lids and module profiles.
  Do not invent unverified fan blades or installed cooling/power components.
- Add a bounded, source-linked catalog of 24 case references across 14 brands
  and five layout families. Manual selection is available. Read SMBIOS only on
  demand and cache whitelisted identity fields; no serial numbers, UUIDs, WMI
  worker, driver, background network lookup or extra hardware poll is added.
  No verified retail-case firmware mappings are available in this first batch;
  unidentified DIY cases remain reference models rather than motherboard guesses.
- Keep the assembly static by default. Optional GPU fan motion uses existing
  fresh RPM feedback and the shared animation clock, pauses outside the visible
  view and releases graphics resources on close. Use Qt Base OpenGL components
  from the existing Essentials dependency, without Qt Quick 3D or Qt 3D.
- Preserve Original's expression-free art, other saved appearances, temperature
  bridge behavior and third-party license rights. Extend the original-art
  noncommercial notice to the generated assembly models and rendering code.

## 0.31.0-preview.1

- Add optional Cream Sticker, Paper Cutout and Blue Ink Journal illustrations,
  with no expressions. Every scheme uses the same 178-entry catalog as Original:
  147 GPUs, 28 RAM modules and 3 CPUs. Existing choices and Original artwork
  remain unchanged; the new schemes are illustrative colors, not factory paint.
- Keep exact reviewed fan geometry, DDR keys and bounded CPU model marks.
  New fan planes reuse the same RPM feedback, shared clock and retained textures;
  unknown blade profiles remain static. Add full-catalog and motion regressions.
- Make the noncommercial scope prominent in README, LICENSING and NOTICE,
  explicitly covering original hardware illustrations and rendering code while
  preserving all third-party and prior-license rights. LICENSE remains unchanged.

## 0.30.0-preview.2

- Correct the four primary artwork choices: Original is the pre-smiley
  Miniature treatment, Cute Smiley is the separate Cartoon treatment, followed
  by Pencil Color and Pen Lines. Keep Smiley Doodle as an additional option.
  No original drawing is repainted or given an expression.
- Expand retained fan-motion regression coverage across every modern treatment,
  including the four primary choices. Preserve measured-RPM timing, stopped
  and stale readings, relative directions and visibility suspension.

## 0.30.0-preview.1

- Add three optional notebook treatments: Loose Pen, Pencil Color and Smiley
  Doodle. Existing artwork and the saved selection remain available. All 178
  catalog entries share their reviewed identities, cooler layouts and memory
  forms across the new treatments; this is a bounded catalog, not every retail SKU.
- Keep sparse, uneven casing lines and transparent pencil gaps instead of a
  technical wireframe. Confirmed fan blades retain their leading curves, tips,
  linked rings and relative directions; unknown blades remain static.
- Distinguish the registered Intel LGA1700 and AMD AM5 front packages. AM5
  models share the same real lid shape and use bounded model marks to differ;
  arbitrary device names never enter SVG text. Notebook artwork adds no
  sampling, animation clock, driver or background service.
- Retain the temperature-startup status fix and scoped style switching from
  the previous prepared build, without requiring a restart to change artwork.

## 0.29.0-preview.3

- Add an optional Hand-drawn Lines treatment with simple slightly uneven ink
  contours and no solid color casing or decorative faces. Existing selected
  illustrations remain unchanged until the user applies another style.

- Update temperature-startup status after a verified fresh CPU reading arrives,
  retaining one consent attempt per app session and the fullscreen deferral.
- Support a bounded local hardware-icon preference change without restarting
  the app or temperature helper. Reject unknown styles, changed instance IDs
  and unsaved settings; use the existing top-bar-only save and rollback.

## 0.29.0-preview.2

- Add optional Cute Cartoon artwork for all 178 current GPU, CPU and memory
  entries, preserving each reviewed enclosure, fan profile and memory key.
  Cartoon quantity and device symbols also cover storage, network, battery,
  cooling and the other existing metric icons without asserting retail models.
- Enlarge modern top-bar GPU drawings from an 18-pixel square to a 30-by-22
  frame at the normal 32-pixel bar height. CPU/RAM icons use 22-pixel frames;
  text spacing, hit regions, grouping and previews share the new width contract.
  Keep Classic/Outline sizing and all five previous artwork choices.
- Reuse retained SVGs, rotor textures and the shared effect clock. No extra
  sampling cadence, hardware scan, frame timer or background service is added.

## 0.28.0-preview.2

- Allow up to 60 seconds for a verified clean shutdown during installation.
  Explicit background installation keeps settings closed even after the previous
  instance has exited; failures log and return an error without a blocking dialog.

- Retain 103 source-linked base GPU representatives across 24 brands, 16 base
  RAM designs across 6 brands, and the 3 CPU examples. Extend matching with
  complete version SKUs: the 56 recorded versions are now supported, with zero
  pending version registrations and 34 explicit artwork registrations, including
  the two earlier SUPRIM 5090 entries and 32 newly implemented versions. The
  runtime catalog contains 178 entries: 147 GPU, 28 RAM and 3 CPU. Support does
  not imply every visual detail is confirmed or every retail SKU is covered.
  See [the generated coverage report](docs/HARDWARE_COVERAGE.json) for exact
  model guards, field-level unknowns, sources and the bounded version inventory.
- Add 16 NVIDIA historical designs from GTX/GT 10 through GTX 900/700/600/500/
  400/200 to GeForce 8800 GTS and FX 5200, plus 20 Radeon/Arc representatives.
  Keep era-specific enclosures tied to exact SKUs instead of reusing a current
  cooler with the same series name. Add generation and product-line filters;
  entry/mainstream/flagship labels describe the board line within its era,
  rather than GPU performance rankings.
- Give Solid, Miniature and Soft distinct major panels, shoulders, end caps and
  illustration proportions for each series. Apply reviewed model colors to
  shrouds, metal panels and rotors instead of treating brand accents as paint.
  Add exposed PCB edges, separated gold-contact segments, bracket outlines and
  narrow heatsink edges without inventing an internal board layout. Electrical
  PCIe lane counts do not imply a mechanically shortened connector.
- Reduce Miniature's exaggerated upper/side extrusion and heavy shadow. Keep
  documented thickness differences through a shallow projection while leaving
  the circular fan plane, fan placement and the other icon versions intact.
- Add on-demand video-port and power-connector technical views with reviewed
  connector types and quantities. These are schematics, not claims about the
  physical port order, socket placement or exact cutouts. Preserve unknown
  interfaces and distinguish verified absence of auxiliary power; documented
  alternative power positions do not become simultaneous extra sockets.
- Share OC/non-OC artwork only for individually reviewed complete SKUs. Verify
  the ROG Astral RTX 5090 standard/OC visible enclosure against the reviewed
  Astral RTX 5080 OC, including official product imagery and external dimensions.
  Give MSI RTX 5090 SUPRIM SOC/OC an independent metal-panel recipe with
  STORMFORCE seven-blade front fans instead of inheriting the RTX 4090 cover.
  Shared artwork never transfers chip identity, memory, power ratings or sensor
  readings between cards. White, copper, rear-power and revision treatments
  retain their own reviewed finishes and structures. The black and white Astral
  front layouts preserve the source-confirmed reversed center fan.
- Retain unconfirmed blade counts for ZOTAC Infinity 5080 10A, GIGABYTE GTX 460
  Rev2/Rev3 and BIOSTAR RX 7600 OC; their fans remain static. BIOSTAR OC's
  unverified cover is explicitly labelled as a technical schematic rather than
  a verified retail enclosure. Version matching can be ready while individual
  appearance fields remain unknown.
- Add on-demand factory-backplate and separate removable-accessory views where
  exact sources support them. Keep GC_HPWR and 16-pin power as alternative
  routes only for the documented SAPPHIRE NITRO+ PhantomLink editions; never draw both as
  simultaneous required sockets. RAM RGB diffuser covers remain static physical
  parts, without claiming the current LED state.
- Distinguish radial blower housings, the Acer BiFrost's left small
  blower/right axial arrangement and fanless fins for confirmed passive cards.
- Add exact-SKU fan profiles to the base GPU representatives and apply reviewed
  version overrides separately. Confirm blades, rotor contours, hubs, rings,
  linked blade groups and relative counter-rotation only from model-specific
  evidence; retain neutral, static faces for unconfirmed blade details.
  Illustration proportions remain visual approximations rather than engineering
  measurements. Current review totals are recorded in the coverage report.
- Correct the modern fan faces: use visibly swept vanes with open curved gaps,
  a recessed dark cavity and an independent cap, rather than bright radial
  discs. Distinguish wide, swept, straight, linked and claw-textured contours;
  align confirmed linked tip arcs with the blade ends and keep fixed shroud
  rings separate from the rotor. Preserve source-confirmed light and dark fans,
  including the distinct SPARKLE A750/B580 TITAN rotors. Label unreviewed active
  fan faces as pending and keep them static; gallery motion requires a reviewed
  face rather than an empty placeholder. The completed export has 119
  motion-ready GPU entries; other active faces retain their unknown status.
- Give the modern leaves longer asymmetric curves and quieter dark-plastic
  shading. Encode the reviewed old MSI TORX seven-wide/seven-narrow pattern;
  preserve the distinct SUPRIM 4090 silver cap, B580 TITAN dark caps, TITAN Luna
  light caps and RDNA3/RDNA4 Taichi center-fan paint. Exact shared versions can
  override their reviewed fan finish without changing live telemetry.
- Animate confirmed visible fans in Solid, Miniature and Soft only when Auto
  receives fresh same-card RPM. Keep a fixed base
  and small retained fan textures; phase changes update local transforms without
  rebuilding shapes or SVG sources. Reuse the existing shared 34 ms clock and
  metric subscription, without adding a timer or raising frame-driven cadence.
  Use fixed 120x slow motion proportional to RPM, independent of usage,
  temperature and effect-speed preferences; zero, unknown and stale RPM stop.
  Never infer current RPM from duty percentage or intended speed. Driver fan
  channels have no verified physical-position mapping, so their card mean drives
  all illustrated front fans and is labelled as a channel mean.
- Add demand-only NVIDIA RPM using existing PCI identity and a read-only NvAPI
  query capped at 1Hz per card, with 5s transient-failure backoff. Prefer the
  private CurrentRpm ABI used by LibreHardwareMonitor v0.9.6, explicitly labelled
  as driver current RPM; fall back to the public single-channel tachometer where
  supported. No administrator prompt, driver, service or control call is added.
  AMD/Intel RPM remains unknown unless a same-card provider supplies it.
- Release rotating layers to the original static illustration when hidden,
  minimized, Off or motion-disabled. Keep Classic/Outline hardware art static
  and CPU/memory load, thermal and electrical channels unchanged. Share the
  details header phase with the expanded 64px illustration without another
  subscription. Gate startup on completed visibility bindings and explicitly
  pause the details header for native-host minimization.
- Extend the existing top-bar RAM metrics and expanded details with memory
  appearances. Preserve unknown form factors and mixed-module identities;
  individual module part numbers do not inherit a kit's design by suffix guesses.
  Physical diffuser covers do not claim current lighting or add RGB animation.
- Keep all five hardware-icon versions in top-bar Appearance settings.
  Preserve the original Classic glyphs and earlier Outline drawings alongside
  Solid, Miniature and Soft. Existing preferences default to Classic. Switching
  versions updates the shared preview and follows the existing scoped Apply flow.
- Add an optional per-item appearance model selection. GPU candidates use the
  currently selected device's cached chip identity, retaining Ti/SUPER/XT and
  other chip distinctions. An explicit choice is labelled Manual appearance;
  clearing it restores automatic matching. RAM artwork can also be selected
  manually. These choices change the illustration only: selected devices,
  metrics, readings and data sources stay intact, with no new discovery query.
  Changing a GPU target clears only that item's manual artwork choice and
  restores automatic matching, preserving its other display preferences.
  A missing secondary GPU never borrows the default GPU or legacy flat identity.
- Distinguish physical fan totals from front-visible fans: opposed MSI EXPERT
  and rear/side auxiliary layouts retain their true totals. Keep the GALAX SG+
  total unknown when auxiliary installation is optional, and keep BIOSTAR's
  unverified layout neutral. Complete reviewed identities establish layouts;
  bare chip names do not automatically select a reference board.
- Preserve confirmed front fans when Qt represents an unknown Python total as
  an undefined QML value. Retain the larger center fans of Advanced and EX Gamer
  representatives and the lowered central FTW3 fan.
- Recognise brand, series and exact-model identities separately. Show series
  shroud motifs and feature summaries in expanded details, with an on-demand
  64px illustration. Unknown fan layouts remain neutral rather than guessed.
- Add an offline, searchable comparison gallery exported from the real QML
  drawing code, including the base entries and ready exact versions, across all
  five icon versions and two themes: 178 entries and 1,780 static SVG variants.
  Retain 18px
  top-bar comparisons and hardware/brand/vendor/generation/product-line filters.
  Add enlarged per-item browsing with Previous/Next and keyboard navigation.
  Keep the page static by default; optional CSS fan preview runs only in view,
  while the page is active and reduced motion is disabled. Interface schematics
  retain their type/count and unverified-position labels. Neither gallery art nor
  a full-card dimension is evidence of a reviewed internal PCB layout.
- Reuse existing identity strings with a bounded offline match cache. Retain PCI
  fields already returned by DXGI without adding monitoring queries or polling.
  The series drawings are static vectors and add no sampling or animation clock;
  real temperature/load effects and hidden/minimized pause behavior remain.
- Keep memory matching pure and acquire Windows module identity separately,
  only when an enabled top bar requests a non-Classic RAM appearance. Attempt
  one bounded SMBIOS snapshot per process using a size query and data read,
  caching failures as well as success. Limit input to 4 MiB and 64 populated
  modules; retain manufacturer/part/form only, without serials, asset tags or
  raw firmware data. Add no SPD/SMBus scan, WMI query, administrator prompt,
  service or polling loop.

## 0.27.0-preview.2

- Restore top-bar background material after returning from administrator
  authorization and when the hidden bar becomes visible again after fullscreen
  avoidance. A successful earlier request does not imply the compositor retained
  the effect across a secure-desktop transition.
- Reapply the existing material in response to those events without adding a
  permanent polling loop or changing sensor/animation cadence.
- Isolate a stalled NVIDIA cleanup call after unavailable GPU readings from the
  sampling worker. Allow only one pending background cleanup, without repeated
  close/reinitialization or normal-path polling; CPU, temperature, network and
  disk sampling can continue while the unavailable GPU source is handled.
- Preserve saved layouts, bar-only mode, fullscreen avoidance and the optional
  read-only ASUS temperature session bridge. New binary/on-device acceptance is
  checked separately from source regressions and offscreen package self-checks.

## 0.27.0-preview.1

- Organize top-bar editing around one live preview and separate Content & layout
  and Appearance tasks. Keep all three designs, material inheritance, continuous
  transparency, existing layouts and optional version-12 hardware effects.
- Show the widget list and desktop actions only when editing desktop widgets.
  Open a saved bar-only profile on the top-bar page when settings are first
  created, while preserving explicit history/widget routes and session navigation.
- Align page content and clarify Saved / Unapplied changes, scoped Apply and
  Discard changes. Keep uncommitted inputs, undo and whole-settings replacement
  boundaries; disable save actions when the current scope has no changes.
- Put on-demand software rankings before expandable CPU logical-processor
  details. Explain missing data directly and keep source limitations and technical
  information available separately. Stop top-bar ranking demand outside its
  visible viewport or when its native host is minimized.
- Pause preview animation subscriptions, optional inspection and history-page
  queries while settings are hidden or minimized. Restore the latest readings
  without discarding group edits, selection or scroll positions. Cosmetic edits
  do not request extra hardware inspection; ordinary sampling is unchanged.
- Retain the machine-specific, read-only ASUS CPU temperature session bridge.
  Add an opt-in Restore CPU temperature at startup preference, disabled by
  default. With an existing ASUS service, request administrator authorization
  once per app session; defer during fullscreen use and do not prompt again in
  that session after cancellation. The bridge exits with its owning app, has no
  startup entry, and does not establish support for every CPU or PC.
- Reuse the application's title controls on the settings Raster host. On the
  tested Windows/Qt path, the native caption background covered the entire
  extended glass frame. An owned-window desktop comparison verified actual
  background blur with the frameless host; the working bar/detail paths remain.

## 0.26.1-preview.9

- Refine optional desktop widgets with clearer hardware headings and static
  accents, more label/value spacing in roomy layouts, slim centered capacity
  tracks and a bounded marker for the current valid history sample.
- Preserve compact layouts, click geometry, true capacity fractions, missing
  and stale data rules. Add no animation clock, polling or material effect.
- Retain preview.8's integration of preview.12 animations/software rankings,
  fullscreen avoidance, read-only ASUS temperature and background work gates.

## 0.26.1-preview.8

- Integrate the separately published 0.26.0-preview.12 development line with
  ASUS read-only CPU temperature, fullscreen game avoidance, hidden-settings
  gates, bounded history batching and the local monitoring optimizations.
- Retain on-demand CPU/RAM/GPU/VRAM top-five software details, asynchronous
  detail compilation, original-layout histories, updated optional hardware
  effects and the bar material/transparency controls from preview.12.
- Keep process rankings out of idle polling, saved preferences, sensor history
  and exports. Network/disk details retain explicit attribution limitations.
- Pause top-bar process ranking demand when its native detail host is minimized.
  Keep preview.12's bounded two-API LUID network snapshot and IPv6 membership,
  adding reset protection for same-name interface replacement and read failure.

## 0.26.1-preview.7

- Reuse the last successful bounded capacities for adapter and legacy interface
  queries, avoiding repeated size-only calls during normal network sampling.
  Resize and retry when the interface inventory grows; retain existing bounds,
  identity checks, fallback behavior and sampling frequency.

## 0.26.1-preview.6

- Suspend optional inspection and live preview projection while settings are
  hidden or minimized. Keep the editing state and list positions alive, and
  refresh from the latest sample on return without waiting for another sample.
- Keep fullscreen avoidance active for a game's same-process or directly owned
  popup while the tracked game window remains visible and fullscreen. Normal
  desktop restoration and stale-window validation remain unchanged.
- Record two low-frequency session events with time, process ID and version:
  successful startup and return from the application event loop. Retain bounded
  warning logs without periodic diagnostic writes.

## 0.26.1-preview.5

- Hide the top bar for foreground fullscreen applications, including a game
  already running when Desktop Stats starts. Reconcile visibility through
  native window events and retain AppBar registration and desktop settings.
- Preserve a running installation's hidden-settings state when upgrading;
  first installation keeps the normal settings launch behavior.

## 0.26.1-preview.4

- Combine requested network reads into one bounded IP-adapter enumeration and
  native counter/status snapshots, retaining FriendlyName membership, 64-bit
  counters and legacy link-state rules. Ambiguous identity uses the existing
  psutil path; failed or replaced interfaces cannot reuse a rate baseline.
- Remove the redundant history-expiry index in the first successful write
  transaction, preserving existing rows, query results, retention, five-second
  batching and WAL durability. Hourly expiry uses the primary-key resolution
  prefix without maintaining a second index on each observation.

## 0.26.1-preview.3

- Refresh the ASUS per-connection sensor snapshot through the read-only
  `Sensors` getter on each two-second read. Reuse the discovered CPU index,
  validate the exact sensor ID/name, and release each snapshot after reading.
  Do not issue monitoring-start, Refresh or hardware-control methods.
- Add synthetic changing-snapshot and identity/failure tests to the bridge's
  nonprivileged self-test. Retain all preview.2 resource reductions.

## 0.26.1-preview.2

- Avoid projecting history/device options while the history page is inactive,
  hidden or minimized; restore the selected device metadata when it opens.
- Request volume capacity only when selected metrics need it. Disk throughput
  keeps its existing sampling and baseline behavior.
- Compute one smoothing coefficient per icon tick and advance only supported
  channels, retaining active phases, cadence, palettes and texture resources.
- Native GUI sampling no longer writes legacy diagnostic files periodically.
  Headless operation retains those exports; IPC diagnostics remain on demand.
- Batch native history writes with a five-second gate, while queries merge the
  bounded in-memory tail. Explicit pause and shutdown attempt to save that tail.
## 0.26.0-preview.12

- Read Windows network counters and operating state through a joined native
  snapshot. Refresh IP-adapter membership and friendly names each poll; join by
  LUID so filter interfaces cannot enter automatic selection and IPv6-only
  adapters remain identifiable. Keep the chosen polling interval, units and
  reset-safe rate calculation. Native failures report their API and safe facts.
- Skip the 40-sample Python/QML history transfer for desktop cards and editor
  previews when their chart is explicitly disabled. Keep current readings live;
  enabling a chart immediately obtains fresh history. Saved desktop settings,
  draft preview settings and resizing freezes keep their existing boundaries.
- Retain the original icons, animation cadence, materials and user settings.

## 0.26.0-preview.11

- Replace per-PID Windows software-usage queries with one bounded native process
  snapshot. Keep fresh creation-time identities, whole-machine CPU accounting,
  working-set semantics and selected-adapter GPU attribution.
- Refresh visible software rankings about once per second without adding query
  time to every interval. Establish the initial CPU rate in a short follow-up;
  give GPU counters their full initial rate window. No idle polling, stale
  generation delivery or catch-up query bursts.
- Precompile top-bar details asynchronously after bars are ready. First-open
  requests share the pending component and remain cancelable; native windows
  and glass retain their existing preparation/cleanup lifecycle.
- Preserve native snapshot API/status failures and distinguish unidentified
  process names from permission failures. Keep original icons and animations.

## 0.26.0-preview.10

- Add descending top-five software rankings to top-bar and desktop-widget
  hardware details. Merge names across processes before ranking. CPU uses a
  whole-machine percentage, RAM uses working-set bytes, and GPU/VRAM readings
  are bound to the selected Windows adapter. Shared memory is explicitly noted.
- Query process activity only while a detail card is visible, on one separate
  worker at a two-second interval. Keep rankings out of preferences, sensor
  diagnostics, history and exports. Closing/replacing cards invalidates late
  replies; PID reuse, counter resets and stale samples do not invent activity.
- Resolve duplicated Windows GPU names through verified physical adapter
  locations, excluding explicitly unlocated name aliases only when a matching
  physical device is known. Ambiguous physical devices remain unavailable.
- Show protected-process coverage and precise native API/error codes. Network,
  disk and non-attributable hardware explain their current limitations rather
  than displaying fabricated per-software percentages or watts.
- Keep original icons, effects, sampling preferences, glass and bar placement.

## 0.26.0-preview.9

- Give RAM/VRAM a proportional light band and ten cool-to-amber colour anchors;
  keep occupied extent independent of effect strength and avoid electrical arcs
  or invented temperature on memory icons.
- Replace network/disk arrow discharges with retained directional data packets.
  Download/read use blue; upload/write use purple. Each real direction controls
  its own density and cadence, with a perceptual small-transfer response that
  never changes the formatted throughput. Disk activity lights use the matching
  direction colour while the neutral drive/arrow geometry stays fixed.
- Give the thermometer ten yellow-to-red anchors and a clearer, softly pulsing
  bulb halo; preserve smooth true column height and clip warmth to its own icon.
- Light the original power-bolt interior in blue between the existing irregular
  current bursts. Keep fixed palette textures and increase packet cadence with
  the real power channel, retaining the user's independent strength/speed.
- Keep CPU/GPU feedback, the fan, battery, original glyphs and assets, shared
  clock, data collection, settings, material behavior and layouts intact.

## 0.26.0-preview.8

- Give the top-bar navigation its own official Lucide panel-top symbol, keeping
  preferences distinct and the original Niangao, CPU and GPU geometry intact.
- In optional hardware feedback, CPU/GPU utilisation above50% and real thermal
  activity warm the hardware body and a tightly clipped surrounding aura. Ten
  warm colour anchors blend continuously; no extra temperature reading is inferred.
- Above50% utilisation, smoothly increase existing irregular yellow/blue packet
  cadence:2x at60%,3x at80%,4x at100%. Higher load also selects denser existing
  atlas stages. Missing heat/power still suppresses its respective discharge.
- Retain the same shared animation clock, image/shader assets, sampling cadence,
  fan and thermometer behavior, saved settings and layouts. Keep aura geometry
  retained across active sensor updates and stop all feedback for reduced motion.

## 0.26.0-preview.7

- Give the native settings caption explicit light/dark fill and text colors so
  its title and standard minimize, maximize and close controls remain readable
  with the extended glass frame. Apply after the guarded client paint, preserve
  the original mode once per surface, and release custom colors to Windows
  defaults during cleanup. Keep native window actions and close-to-tray behavior.
- Use an explicit low-tint Acrylic compatibility carrier for the bar, settings
  and details. Keep the continuous foreground transparency control independent
  from icon/text opacity. Ordinary widget and default Raster blur remain on their
  existing carrier; dragging the slider adds no native request or timer.
- Replay a theme changed inside native setup once; if it changes again, clear
  safely and use the existing bounded recovery with the latest theme. Do not
  cache that transient fallback. Continue caption restoration after ordinary
  cleanup read errors, while never crossing ownership or surface generations.
- Preserve original icons, animation assets and cadence, profiles, sampling,
  history and layouts. Own-window native-caption renders and isolated behavior
  checks do not certify the active desktop compositor's glass appearance.

## 0.26.0-preview.6

- Keep bar material and continuous 0–100% transparency controls visible without
  opening secondary settings. Editing an inherited slider makes only the bar
  independent. Apply saves the bar branch; global/widget drafts remain separate.
- Use a lighter bar-only coating, shared by the real band and its previews.
  Paint only existing bands/details during preview, with no metric-model update,
  AppBar placement, extra timer or per-step native blur reconfiguration. Restore
  saved appearance on hide; replay the latest preview after reentrant refresh.
- Use the existing activation-independent Raster compatibility blur for settings
  and details, keeping the transparent foreground and WUJI-style reading planes.
  Prepare before first Show, retain generation/ownership and cleanup guards, and
  use a readable solid fallback when the native request fails. Native API success
  and offscreen tests do not certify the desktop compositor's appearance.
- Retain original icons, animations, shader assets, profile, collection and history.

## 0.26.0-preview.5

- Composite the existing four arc-atlas cells in one RHI shader quad, preserving
  premultiplied source-over order, inherited opacity, stage/frame interpolation,
  atlas artwork and cadence. Retain the original four-image path for software
  rendering and shader errors. Include the original GLSL and generated Qt asset.
- Stop calculating unrelated phases in composite fan ticks. Keep the existing
  per-frame rotor, positive-reading continuity, speed controls and stopping rules.
- Preserve configuration, data collection intervals, device sources and history.

## 0.26.0-preview.4

- Move continuous fan rotation to frame-driven updates in the existing shared
  per-window clock. Keep other effects at their previous bounded cadence; use
  the original background timer when no continuous rotor is subscribed. The
  two drivers run exclusively and retire with the last active subscriber.
- Preserve phase and subscriptions during positive readings and speed changes.
  Bound delayed rotor steps below the four-blade half pitch to avoid apparent
  reversals, without restarting a duration-based animation on every sample.
- Rotate the retained fan layers with one parent transform and update only its
  relevant feedback channel per frame. Preserve the existing icons, palettes,
  strength/speed settings, stopping rules and sensor sampling frequency.

## 0.26.0-preview.3

- Add a validated installed profile pointer and stable production IPC identity,
  so launch contexts can share one explicitly selected profile. Explicit test
  data directories remain isolated. Invalid pointers fail clearly; no automatic
  profile merging, migration or silent reset. Preserve pointers on upgrades and
  read autostart from the selected profile. Add path-free identity diagnostics.
- Make high fan speeds visibly faster with smooth speed changes and a subtle
  retained rotor trail. Preserve the shared clock, phase and stop/reduced-motion
  rules; bound the visual rate to avoid four-blade stroboscopic reversal.
- Pass through genuine LibreHardwareMonitor Noise / dBA channels, expose them
  with a sound icon and cooling-detail context. Missing sources remain explicit;
  do not infer sound pressure from RPM or enable a microphone or extra drivers.
- Keep group, duplex and settings-preview icon delegates alive across ordinary
  readings. Replace their models only when ordered membership changes; numeric
  values and hardware channels continue updating through live bindings. Preserve
  animation phases and clock subscriptions between samples, with smooth target
  changes and the existing zero/missing/hidden/reduced-motion stopping rules.
- Avoid a transient non-duplex state when switching between two-line and inline
  paired readouts. Keep drag freezing, structural changes and layout measuring
  separate from ordinary value updates, without adding animation timers.
- Add a visual guide and reproducible light/dark GIFs covering hardware effects,
  display styles, optional controls and material limitations. Demonstrations use
  synthetic data and offscreen QML; they are not native rendering benchmarks.

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
# 0.26.1-preview.1 — optional ASUS CPU temperature

- Adds an explicitly authorized, read-only ASUS CPU cache bridge for the fixed
  `CPU / 0x06030012` sensor. It reuses an already-running ASUS COM service and
  never starts monitoring, changes fan controls, or installs a driver/service.
- One retained sensor getter runs every two seconds. The ordinary app reads a
  64-byte shared snapshot, rejects failed/future/stale observations, and preserves
  source times for history deduplication. The bridge exits with its bound app.
- Adds protocol, source failure, freshness, sampling-limit and history/fallback
  regressions; existing native layout and per-section settings remain in use.

