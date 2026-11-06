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

Solid, Miniature and Soft share dedicated series casing profiles: broad panel
divisions, end shapes, shoulders and illustration proportions, rather than just
different accents. Their front-view fans follow the reviewed visible layout;
contacts and brackets remain small. All versions consume the same identity map
and real readings. Choosing a version changes
the draft and shared preview; the existing top-bar Apply action persists it.
The source-export tools include a synthetic offscreen comparison renderer,
`tools/render_hardware_styles.py`, which never opens a desktop window.

## Matching and truthfulness

- CPU manufacturer and GPU chip vendor are different from the manufacturer of a
  complete graphics card. A motherboard's ASUS identity says nothing about a GPU.
- The current catalog recognises 22 brand identities and 67 GPU series/product
  lines, with one reviewed GPU representative per entry. Together with 3 CPU
  examples, that is 70 model records, each with an official reference URL.
  This is a bounded catalog, not coverage of every current or historical SKU.
  The CPU examples do not establish coverage of all processor families.
- Each GPU series has a dedicated static casing profile in Solid, Miniature and
  Soft. Expanded details provide up to two short feature descriptions and an
  on-demand larger illustration. These summarize the cited representative's
  design language; geometry can differ across generations, revisions and SKUs.
  Outline remains the preserved earlier version.
- A complete reviewed model/SKU alias can supply a verified cooler layout.
  A series or brand match alone never assigns physical fans. A matching SKU
  still keeps unknown fields unknown when its source does not confirm them.
  Brand-only matches receive a neutral silhouette and a restrained UI accent.
- A GPU revision, white edition, BTF version or nearby model must have its own
  reviewed alias. A GPU chip name, sensor row count and fan speed of zero cannot
  prove the number of physical fans.
- Bare chip names do not prove a reference board. Founders Edition, AMD Reference
  / Made by AMD and Intel Limited Edition require their explicit reviewed
  identities; an ordinary NVML name is not silently treated as one of them.
- Laptop/integrated GPUs use a chip silhouette and no desktop-card fan assembly.
- Multi-GPU projection reads the selected row. Missing devices remain generic;
  another device or legacy flat GPU data cannot supply a selected secondary GPU.
- Bound external sensors retain their own identity and existing glyph semantics.
- The details metadata distinguishes model, series, brand and generic appearance.
  It separates the physical total from fans visible on the illustrated front.
  Neither field is derived from the number of circles drawn by the UI.

### Total and front-visible fans

| Reviewed representative | Physical total | Front-visible |
| --- | ---: | ---: |
| ASUS ROG Astral RTX 5080 OC | 4 | 3 |
| MSI RTX 4080 SUPER EXPERT | 2, on opposite faces | 1 |
| GALAX HOF RTX 5080 Extreme | 4 | 3 |
| INNO3D iCHILL X4 RTX 3080 | 4 | 3 |
| GALAX SG+ RTX 4070 Ti SUPER | Unconfirmed: auxiliary fan is optional | 3 |
| BIOSTAR Radeon RX 7600 VA7606RM81 | Unconfirmed | Unconfirmed |

Optional auxiliary fans do not prove what a user installed. Unknown is not zero,
and unknown layouts do not borrow a fan count from the family name or a nearby
model. The classic generic glyph does not depict a physical fan layout.

## Offline review gallery

Generate a self-contained HTML comparison using the project's Python environment:

```console
python tools/export_hardware_gallery.py --output qa-private/hardware-gallery.html
```

Use `--overwrite` when deliberately replacing an existing export. The current
gallery embeds 670 static SVG variants: 67 GPU representatives × 5 icon versions
× 2 themes. It supports brand filtering, model/series search, style and background
selection, large illustrations and an 18px top-bar comparison. CPU examples are
not included in this GPU gallery.

The exporter uses the actual QML drawing code without starting the installed
application, sampler, native desktop windows or hardware discovery. The generated
page works offline; only following an official-source link opens an external
site. The gallery is a separate review artifact, not a resident app window.

## Runtime cost

`hardware_appearance.py`, `hardware_series.py` and the catalog data modules are
offline, with no system queries, threads, polling, network access, privilege
changes or hardware-monitoring dependencies. Matching consumes
existing cached CPU names and already delivered GPU identities. A bounded cache
holds at most 128 immutable matches. Optional `board_vendor` and `board_model`
fields must describe the selected GPU. They are not currently supplied by the
standard NVML provider, so common NVML chip names correctly fall back to a brand
outline rather than claiming a precise retail cooler.

`process_gpu.dxgi_adapters` retains four PCI identity integers that GetDesc1 already
returned; this does not start Top 5, add an API call or resolve a retail SKU by itself.
No new NVML query is introduced into the sampling path.
The series shape modules only generate static geometry when the existing
appearance key changes. They do not discover devices, infer fans, animate, add
an animation clock or poll hardware.

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

Add a record to the catalogs aggregated by `hardware_appearance.CATALOG` after checking an official
product page for the exact model/revision. Keep an official URL, complete aliases,
chip vendor, board manufacturer, a confirmed physical fan count or `None`, and an
appropriate silhouette. Record front-visible fans separately for opposed,
back-mounted or optional auxiliary layouts; do not substitute them for the total.
Run the matcher and QML tests, including negative tests for adjacent capacities,
revisions and mobile products. Do not use a family-wide substring to assign fans.
Reviewed models live in `hardware_model_extensions.py` and the grouped/core
catalog modules, with explicit model-to-series maps. WHITE, LIQUID, LIMITED, BP and laptop names do not
inherit the standard model's fan count; they require their own reviewed entries.

At present the stock sensor path automatically identifies chip/CPU brands; retail
board-level matches require a complete model identity from a provider. An offline
PCI-subsystem catalog can be added later when its exact SKU mapping is verified.
No online recognition service or full motherboard scan is enabled for this feature.
