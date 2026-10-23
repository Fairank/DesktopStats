# Third-party notices

## Lucide UI symbols

The interface's CPU, GPU, memory, battery, power, cooling, temperature, noise,
electrical-meter, frequency, time, directional network/disk, and control symbols
use selected unmodified SVG geometry from **Lucide 1.61.0**, by Lucide
Icons and Contributors. These are UI symbols, separate from the approved
Niangao application identity.

- Official repository: https://github.com/lucide-icons/lucide
- Fixed upstream commit: `c29c276f16590cf017126671535ad8c792be64d8`
- Complete upstream license and copyright notices: `assets/lucide/LICENSE`
- Original source files: `assets/lucide/icons/`
- Source URLs, aliases, and file hashes: `assets/lucide/provenance.json`

Lucide is distributed under the ISC License. Its upstream license also lists
Feather-derived icons subject to the MIT License and Cole Bemis's copyright
notice. The complete original license file is included unchanged; the
application's PolyForm Noncommercial license does not replace either notice
or restrict the independent rights granted for these upstream icons.

`native/IconData.js` retains the original SVG child elements. The Qt wrapper
supplies inherited stroke color, a two-unit stroke, round caps/joins, and
display size. It does not redraw the paths. No icon font, remote asset service,
or network connection is required at runtime.

## Three r150 noise and lightning algorithms

Optional icon-discharge artwork uses adapted algorithms from **three.js r150**,
copyright © 2010-2023 three.js authors, under the MIT License.

- Fixed upstream commit: `9b274fef1d2b9ba0fc47410d06593e1f34f4df0e`
- Original files: `third_party/threejs/r150/SimplexNoise.js` and
  `third_party/threejs/r150/LightningStrike.js`
- Complete MIT text: `licenses/three-r150/LICENSE.txt`
- Original source hashes: `licenses/three-r150/SOURCES.json`
- Translated subset and local changes: `licenses/three-r150/NOTICE.md`

`tools/three_simplex4d.py` translates the used 4D noise tables, permutation
initialization and `noise4d` routine. The original credits for Stefan Gustavson
and Sean McCullough remain with that module. `midpoint_ray` in
`tools/generate_metric_motion.py` adapts `LightningStrike.fractalRayRecursive`
to deterministic artwork centerlines; it does not reproduce the mesh runtime.
These identified upstream-derived portions retain their MIT rights, including
commercial permissions independently granted by that license. The application
license does not replace the MIT notice or relicense the original files.

The surrounding burst choreography, palettes, Gaussian light composition and
atlas packing are project-authored. `assets/metric-motion/manifest.json` records
the generator, noise module, parameters and output hashes. Keep this attribution
with the generated artwork; this does not claim that arbitrary output of MIT
software automatically inherits its software license. Runtime playback uses
local PNG textures in Qt; neither Three.js nor a browser is an application
runtime dependency. Pillow is used only by the optional artwork generator.

## Other dependencies

The original application uses PolyForm Noncommercial 1.0.0 from
0.19.0-preview.1. This does not apply that restriction to dependencies or
withdraw rights in earlier MIT-licensed copies. The Niangao identity retains
its prior/upstream permissions. See `LICENSING.md` and `assets/ICON-NOTES.md`.

A packaged distribution also contains `THIRD_PARTY_LICENSES.txt` for its
Python/Qt components and `_internal/collector/THIRD-PARTY-NOTICES.md` for the
separately loaded hardware collector libraries. Their complete notices and
corresponding-source references remain applicable.
