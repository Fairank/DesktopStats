# Three r150 algorithm adaptations

Upstream: https://github.com/mrdoob/three.js

Fixed commit: `9b274fef1d2b9ba0fc47410d06593e1f34f4df0e` (`r150`).

Copyright © 2010-2023 three.js authors. The complete, unmodified MIT License is
included in `LICENSE.txt` beside this notice. `SOURCES.json` records the exact
upstream file hashes. Original source files are retained in
`third_party/threejs/r150/` for review and attribution, not loaded at runtime.

## Used source and translated subset

- `examples/jsm/math/SimplexNoise.js` → `tools/three_simplex4d.py`: the used
  `grad4` and simplex traversal tables, permutation initialization, `dot4`, and
  `noise4d` logic. The module retains MIT and the original Stefan Gustavson /
  Sean McCullough attribution comments. Local changes expose a Python API and
  deterministic local seeding, without changing the shared-permutation noise
  definition. Other noise dimensions and unused JavaScript APIs are omitted.
- `examples/jsm/geometries/LightningStrike.js`, `fractalRayRecursive` →
  `tools/generate_metric_motion.py`, `midpoint_ray`: recursive free XYZ
  midpoint displacement, per-level roughness and 4D noise. Local changes return
  centerline points for offline 2D artwork instead of building Three geometry;
  very short segment lengths use a local minimum of 0.01 rather than the
  upstream near-zero-only fallback. Radius, up-vector and mesh-fraction work
  are omitted; this is an adaptation, not full numerical/runtime equivalence.
  no `BufferGeometry`, material, WebGL or mesh runtime is bundled. The generator
  explicitly identifies the MIT-derived algorithm and includes its notice.

The generator's anchor placement, localized burst scheduling, decorative stage
parameters, branches, light composition and file packing are project-authored.
Those additions do not remove rights in the identified MIT portions. Any future
translation of further upstream routines must update this derivation list.

## Artwork and runtime

`assets/metric-motion/manifest.json` records the exact generator/noise hashes,
seeds, dimensions, stage recipe and hashes of the two generated PNG atlases.
Attribution accompanies these derived resources as a distribution policy; it is
not a statement that all output of MIT software inherits the software license.

`native/MetricIcon.qml` implements project-authored Qt playback and real-data
guards. The application does not execute the upstream JavaScript, ship Three.js
as a browser dependency, or require Pillow at runtime. Pillow is an optional
artwork-generation tool. React Bits and Expo component implementations are not
included in these product sources or textures.
