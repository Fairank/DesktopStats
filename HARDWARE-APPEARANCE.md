# Hardware appearance catalog

The top bar can use small original hardware silhouettes without changing metric
meaning, live temperature, load colours or the existing motion clock. CPU, GPU
and RAM appearances also reach the expanded hardware details. These are
stylised illustrations, not product photos, official logos or manufacturing drawings.
Small brand accents are UI colours, not a claim about a card's physical colour.

## Selectable icon versions

Top bar → Appearance → Hardware icons offers five versions:

- `classic`: the original generic Lucide glyphs; the default for existing settings.
- `outline`: the previous original line drawings, preserved as an explicit option.
- `solid`: simplified physical objects, filled metal shrouds and clear fan wells.
- `miniature`: visible top/side thickness and fixed geometric shadows, without filters.
- `soft`: rounder, two-tone objects with broad shapes and separated fan blades.

Solid, Miniature and Soft share dedicated series casing profiles: broad panel
divisions, end shapes, shoulders and illustration proportions, rather than just
different accents. Their front-view fans follow the reviewed visible layout;
contacts and brackets remain small. All versions consume the same identity map
and real readings. Radial blowers use an impeller rather than an axial-fan
symbol. The reviewed Acer BiFrost combines a small left blower and a right axial
fan; reviewed passive cards have no fan. Memory designs distinguish exposed
boards, low heatspreaders, taller enclosures and physical diffuser covers.
These shapes do not introduce lighting effects or report the current LED state.
Choosing a version changes
the draft and shared preview; the existing top-bar Apply action persists it.
The source-export tools include a synthetic offscreen comparison renderer,
`tools/render_hardware_styles.py`, which never opens a desktop window.

## Matching and truthfulness

- CPU manufacturer and GPU chip vendor are different from the manufacturer of a
  complete graphics card. A motherboard's ASUS identity says nothing about a GPU.
- The GPU catalog contains 103 dedicated designs and 103 reviewed GPU models
  across 24 GPU brand identities. The memory catalog adds 16 designs and 16
  complete reviewed part numbers across 6 memory brands. Together with 3 CPU
  examples, that is 122 model records and 119 GPU/memory designs, with 30 brand
  identities across the GPU and memory catalogs and official reference URLs.
  This is a bounded catalog, not coverage of every current or historical SKU.
  The CPU examples do not establish coverage of all processor families.
- Each GPU series has a dedicated static casing profile in Solid, Miniature and
  Soft. Expanded details provide up to two short feature descriptions and an
  on-demand larger illustration. These summarize the cited representative's
  design language; geometry can differ across generations, revisions and SKUs.
  Outline remains the preserved earlier version.
- Historical additions include 16 NVIDIA designs from GTX/GT 10 through GTX
  900, 700, 600, 500, 400 and 200 to GeForce 8800 GTS and FX 5200. Another 20
  Radeon/Arc designs span Radeon HD, R9, Polaris, Vega, RDNA and Intel Arc.
  These are specific reviewed representatives, not every card in those eras.
  Exact SKU maps keep an older GAMING, LIGHTNING, NITRO or STRIX enclosure
  separate from a current design with the same long-lived line name.
- Generation and entry/mainstream/flagship/reference metadata describe the
  representative and its board product line within that era. They are gallery
  filters, not a ranking of GPU chip performance across manufacturers or years.
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

### Decorative fan motion

The 100 reviewed GPU models with confirmed visible impellers can supply separate
fan layers in Solid, Miniature and Soft. Axial fans, radial blowers and mixed
layouts retain their own positions and sizes, including opposed-face and
auxiliary-fan layouts. Unknown layouts and passive cards have no rotating layer.
Classic and Outline keep their existing static hardware drawings.

Rotation is a decorative response to the existing icon effect and available
activity channels. It does not report measured RPM or establish whether a real
fan is currently spinning. CPU and memory load/thermal/electrical feedback keeps
its existing channel semantics.

### Memory identity and limits

The 16 reviewed memory part numbers cover CORSAIR, G.SKILL, Kingston, Crucial,
TEAMGROUP and ADATA/XPG representatives. A complete reviewed part number can
select its model; a confirmed manufacturer and unambiguous series phrase can
select a series illustration. Kit part numbers and individual module part
numbers remain distinct. No suffix is removed to turn an unreviewed module into
a reviewed kit, and firmware's G.SKILL module identity alone does not establish
the enclosure shown on a kit's official page.

An unknown form stays neutral. DDR generation, capacity, speed and motherboard
brand do not establish DIMM versus SO-DIMM, heatspreader shape, chip count or
lighting. Mixed or conflicting installed modules use a mixed/generic identity
rather than selecting the first module as the machine's appearance. A missing
official product image also leaves that representative's unverified enclosure
neutral. RAM's existing usage/capacity readings and effects retain their meaning.

## Offline review gallery

Generate a self-contained HTML comparison using the project's Python environment:

```console
python tools/export_hardware_gallery.py --output qa-private/hardware-gallery.html
```

Use `--overwrite` when deliberately replacing an existing export. The current
gallery includes all 122 reviewed model entries and 1,220 complete static SVG
variants: (103 GPU + 16 memory + 3 CPU representatives)
× 5 icon versions × 2 themes. It supports hardware type, brand, GPU chip vendor,
generation and product-line filters, model/series search, style and background
selection and an 18px top-bar comparison. Open any illustration for a larger
view, then browse the filtered items with Previous/Next or the left/right arrow
keys; Home/End reaches the first/last item.

The gallery opens with static illustrations. Its optional motion preview uses
the prebuilt base and fan layers of the 100 eligible GPU models, with CSS
rotating only the small fan images. It runs only for visible illustrations while
the page is active and the system does not request reduced motion. Leaving the
viewport, hiding/suspending the page or requesting reduced motion stops it.
Classic, Outline, CPU, memory, unknown layouts and passive cards remain static
in this gallery preview. This offline preview is illustrative, without live
hardware readings or measured fan speeds.

The exporter uses the actual QML drawing code without starting the installed
application, sampler, native desktop windows or hardware discovery. The generated
page works offline; only following an official-source link opens an external
site. The gallery is a separate review artifact, not a resident app window.

## Runtime cost

`hardware_appearance.py`, `memory_appearance.py`, `hardware_series.py` and the catalog data modules are
offline, with no system queries, threads, polling, network access, privilege
changes or hardware-monitoring dependencies. Matching consumes
existing cached CPU names and already delivered GPU identities. Each identity
matcher caches at most 128 immutable matches. Optional `board_vendor` and `board_model`
fields must describe the selected GPU. They are not currently supplied by the
standard NVML provider, so common NVML chip names correctly fall back to a brand
outline rather than claiming a precise retail cooler.

Memory identity acquisition is a separate, demand-gated operation in
`memory_identity.py`. An enabled top bar configured with a RAM metric and any
of the four non-Classic icon versions can request it. On Windows it attempts
one read-only SMBIOS snapshot per process: one size query and one data read via
`GetSystemFirmwareTable('RSMB')`, at most two API calls. Success and failure are
cached, so later projections do not retry or poll. Classic-only configurations
and configurations without an eligible top-bar RAM metric do not request this
read.

The snapshot is bounded to 4 MiB and 64 populated memory devices. Only Type 17
manufacturer, complete part number and form factor survive parsing; serial
numbers, asset tags and the raw firmware buffer are not retained or written.
Malformed, oversized or unavailable data leaves the appearance unknown. This
path does not read SPD/SMBus, invoke WMI, request administrator rights, install a
service or add a monitoring thread or timer. The firmware interface and Type 17
layout are documented by [Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemfirmwaretable)
and [DMTF SMBIOS 3.9.0, section 7.18](https://www.dmtf.org/sites/default/files/standards/documents/DSP0134_3.9.0.pdf).

`process_gpu.dxgi_adapters` retains four PCI identity integers that GetDesc1 already
returned; this does not start Top 5, add an API call or resolve a retail SKU by itself.
No new NVML query is introduced into the sampling path.
The series shape modules only generate static geometry when the existing
appearance key changes. They do not discover devices, infer fans, animate, add
an animation clock or poll hardware.

The shape identity and geometry key remain independent of dynamic
`hardware_state` and rotation phase. `HardwareGlyph` defaults to one complete
static SVG image. For a visible GPU in a modern style, a confirmed fan layout
and an active Auto/Pulse effect can replace it with one fixed base plus one
small retained texture per visible fan. Only each fan's local transform rotates;
the casing and discs stay fixed. Equal identity samples and phase updates do not
rebuild the key, SVG sources or fan-layer geometry. Only the selected icon version
loads its textures; inactive versions do not allocate image sets.

`MetricIcon` uses its existing subscription to the shared 34 ms background
clock. GPU motion adds no subscription, timer or frame-driven cadence. Hidden,
minimised, Off and motion-disabled states release the rotor Loader and return
to the complete static illustration. Completion/exposure readiness gates let
bound visibility settle before activating motion, avoiding an initialization
binding cycle. Existing CPU/memory feedback and all real metric values remain
independent of fan phase. Transform updates and compositing still have a cost;
avoiding SVG regeneration is not a claim of zero CPU or GPU work.

The 64px details illustration exists only while its metadata is expanded and its
window is visible, and is released on collapse, hiding or minimisation. Its fans
reuse the details header's existing phase and add no clock subscription. An
explicit native-host minimised flag also pauses that header when Qt's own window
visibility remains unchanged. Other metrics keep their existing glyphs, and the
original Lucide data remains unchanged.

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
Memory uses the bounded firmware identity path described above and retains a
neutral result for an unreviewed part or inconsistent modules. No online
recognition service or full motherboard scan is enabled for this feature.
