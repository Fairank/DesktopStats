# Desktop Stats icon

The face is the existing user-approved Niangao identity from [Fairank/FieldDock, branding/niangao-v1.svg](https://github.com/Fairank/FieldDock/blob/main/branding/niangao-v1.svg). Its complete black `evenodd` path is reused unchanged at every size. Only uniform scale, placement, a white rounded tile, and a separate short blue status pulse are applied. Face shape, eyes, nose, fur markings, and black-and-white colors are not redrawn or simplified.

`niangao-source.svg` is the original repository file, Git blob SHA `4bc4949f8f807b54eb3801e54e3cdbb88d212588`. Its face-path SHA-256 is `974330e09361a6b6bc2df3fe16f8ace94c8b09719c2e703c8d2871d2e354d27e`. The upstream branding README records that this vector traces the approved AI-assisted master, whose PNG SHA-256 is `187738542cc2ea14bfb01165dacbc974479dd0d5b0aa6698a0179235dfb1e737`. No personal photograph is bundled. AI-assisted identity provenance is retained; no exclusive-rights guarantee is claimed.

The earlier geometric black-cat redraw was rejected by the user and is withdrawn. None of its face paths belongs in the release assets. It is retained only in private QA history, outside the distribution.

## Optical sizes

The same original face path and its proportions are retained at 16, 20, 24, 32, 40, 48, 56 px, and all larger sizes. Tile padding, uniform face placement, and the status pulse's position and weight are calibrated for those native sizes. Every PNG is rendered directly from its vector composition at its final dimensions, without enlarging the previous raster icon. Fine details necessarily have fewer pixels at small sizes; no claim is made that tiny fur marks remain individually distinguishable.

- `niangao-source.svg`: unchanged approved FieldDock vector identity.
- `icon.svg`: composed large SVG master, with a 1024 px viewport.
- `icon-<size>.svg` and `icon-<size>.png`: native-size vector and directly rendered PNG pairs for 16, 20, 24, 32, 40, 48, 56, 64, 96, 128, 256, 512, and 1024 px.
- `icon.png`: byte-for-byte alias of `icon-1024.png` for existing image references.
- `icon.ico`: eleven separate 32-bit PNG frames, 16–256 px, including 20, 24, 40, 48, and 56 px. Each frame is the matching native-size PNG, not an ICO encoder's resize of another frame.
- `icon-manifest.json`: file hashes, optical tiers, and the generator's hash.

Use the ICO for Windows application, tray, and window icons. For a 20 px QML image, prefer `icon-20.svg`; use `icon-32.svg` for the existing 27 px brand mark. The SVG remains sharp at fractional scale, while Windows can choose an exact ICO frame at common DPI settings.

## Reproduction and limits

Run `.venv\Scripts\python.exe tools\generate_icons.py` to regenerate the assets. Add `--check` to verify them without writing, or `--proof qa-private/redesign18/icon-taskbar-proof.png` for the optional asset-only proof. Rendering uses the installed Qt SVG renderer on the offscreen platform. The tool creates no windows and does not read user preferences or contact any service.

The asset proof checks native-size appearance, decoded ICO frames, and alpha boundaries. It is not a screenshot or verification of the installed Windows taskbar, Windows icon cache, native compositor, or application identity integration.
