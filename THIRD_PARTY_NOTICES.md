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

## Other dependencies

The original application uses PolyForm Noncommercial 1.0.0 from
0.19.0-preview.1. This does not apply that restriction to dependencies or
withdraw rights in earlier MIT-licensed copies. The Niangao identity retains
its prior/upstream permissions. See `LICENSING.md` and `assets/ICON-NOTES.md`.

A packaged distribution also contains `THIRD_PARTY_LICENSES.txt` for its
Python/Qt components and `_internal/collector/THIRD-PARTY-NOTICES.md` for the
separately loaded hardware collector libraries. Their complete notices and
corresponding-source references remain applicable.
