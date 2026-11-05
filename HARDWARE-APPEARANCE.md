# Hardware appearance catalog

The top bar can use small original hardware silhouettes without changing metric
meaning, live temperature, load colours or the existing motion clock. These are
stylised illustrations, not product photos, official logos or manufacturing drawings.
Small brand accents are UI colours, not a claim about a card's physical colour.

## Selectable icon versions

Top bar → Appearance → Hardware icons offers five versions:

- `classic`: the original generic Lucide glyphs; the default for existing settings.
- `outline`: the previous original line drawings, preserved as an explicit option.
- `solid`: simplified physical objects, filled metal shrouds and clear fan wells.
- `miniature`: visible top/side thickness and fixed geometric shadows, without filters.
- `soft`: rounder, two-tone objects with broad shapes and five separated fan blades.

The three new versions use a short card for a confirmed single fan, a longer card
for two and a slimmer, long card for three. Contacts and brackets remain small.
They consume the same identity map and real readings. Choosing a version changes
the draft and shared preview; the existing top-bar Apply action persists it.
The source-export tools include a synthetic offscreen comparison renderer,
`tools/render_hardware_styles.py`, which never opens a desktop window.

## Matching and truthfulness

- CPU manufacturer and GPU chip vendor are different from the manufacturer of a
  complete graphics card. A motherboard's ASUS identity says nothing about a GPU.
- A complete reviewed model alias selects its package/cooler silhouette. The
  catalog has 3 CPU and 14 GPU models; each record has an official reference URL.
- A separate catalog recognises 14 graphics-card series across ASUS, MSI,
  GIGABYTE, ZOTAC, SAPPHIRE and PowerColor. Series motifs retain distinctive
  shroud lines and accents; two short feature descriptions and a larger static
  illustration are available in expanded details metadata. These are family
  design-language summaries based on the cited representative products, not a
  promise of identical geometry across every generation, revision or SKU.
- Every one of those 14 series now has a reviewed exact representative SKU and
  a dedicated static casing profile: independent end caps, shoulders, large panel
  divisions and proportions. These replace the three shared casing categories
  in Solid, Miniature and Soft. Outline remains the preserved earlier version.
- There are 22 recognised brand identities. Brand-only matches receive an accent
  and a neutral silhouette, never a guessed fan arrangement or cooler shroud.
- A GPU revision, white edition, BTF version or nearby model must have its own
  reviewed alias. A GPU chip name, sensor row count and fan speed of zero cannot
  prove the number of physical fans.
- Laptop/integrated GPUs use a chip silhouette and no desktop-card fan assembly.
- Multi-GPU projection reads the selected row. Missing devices remain generic;
  another device or legacy flat GPU data cannot supply a selected secondary GPU.
- Bound external sensors retain their own identity and existing glyph semantics.
- The details metadata distinguishes model, series, brand and generic appearance. Its fan
  count is shown only for an exact model with a reviewed physical layout.

## Runtime cost

`hardware_appearance.py` and `hardware_series.py` are offline with no system queries, threads, polling,
network access, privilege changes or hardware-monitoring dependencies. It consumes
existing cached CPU names and already delivered GPU identities. A bounded cache
holds at most 128 immutable matches. Optional `board_vendor` and `board_model`
fields must describe the selected GPU. They are not currently supplied by the
standard NVML provider, so common NVML chip names correctly fall back to a brand
outline rather than claiming a precise retail cooler.

`process_gpu.dxgi_adapters` retains four PCI identity integers that GetDesc1 already
returned; this does not start Top 5, add an API call or resolve a retail SKU by itself.
No new NVML query is introduced into the sampling path.
`HardwareSeriesShapes.js` only generates geometry when the existing appearance
key changes. It does not discover devices, infer fans, animate or poll hardware.

The appearance is independent of dynamic `hardware_state` and the icon effect
switch. QML retains a single static SVG image per active hardware glyph, with a
stable geometry key that includes the selected version. Same-value samples do
not rebuild the image. Only the selected version produces a texture; the other
versions do not run animations or load image sets. The existing load/thermal/electrical layers keep their own
values and clock, including hidden/minimised pause behaviour. Unknown/non-CPU/GPU
metrics keep their existing glyphs. The original Lucide data stays unchanged.
The 64px details illustration exists only while its metadata is expanded and its
window is visible, and is released on collapse, hiding or minimisation.

## Extending coverage

Add a record to `hardware_appearance.CATALOG` only after checking an official
product page for the exact model/revision. Keep an official URL, complete aliases,
chip vendor, board manufacturer, physical fan count and an appropriate silhouette.
Run the matcher and QML tests, including negative tests for adjacent capacities,
revisions and mobile products. Do not use a family-wide substring to assign fans.
Additional reviewed models live in `hardware_model_extensions.py`, with an
explicit model-to-series map. WHITE, LIQUID, LIMITED, BP and laptop names do not
inherit the standard model's fan count; they require their own reviewed entries.

At present the stock sensor path automatically identifies chip/CPU brands; retail
board-level matches require a complete model identity from a provider. An offline
PCI-subsystem catalog can be added later when its exact SKU mapping is verified.
No online recognition service or full motherboard scan is enabled for this feature.
