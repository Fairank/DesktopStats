# Part models

Drop part `.glb` files here and wire them up in `src/lib/gltfModels.js`
(`FILES`) plus `src/lib/partSpecs.js` (`PART_SPECS`). `src/tests/modelBounds.test.js`
asserts every recorded `raw` bounding box still matches the shipped mesh, so a
re-export or a swapped model fails loudly instead of silently mis-scaling the
whole assembly.

Models not yet wired up live in `/models-staging/` at the repo root — kept out of
`public/` so they aren't copied into `dist/` and uploaded on every deploy.

## Attribution

These models are used under **CC Attribution 4.0** (CC-BY), which requires credit.

The user-facing credits live in `MODEL_CREDITS` (`src/lib/siteContent.js`) and are
rendered on the Help page. `src/tests/modelCredits.test.js` asserts every `.glb`
here has a credit with an author, a title and a Sketchfab source — so adding a
model without crediting it fails the suite rather than quietly infringing.

| File | Model | Author | Source |
| --- | --- | --- | --- |
| `fan.glb` | 120mm Computer Fans | kusuma844 | https://sketchfab.com/3d-models/120mm-computer-fans-6c17bfc4a2a5438eb9996fb3c73e1a91 |
| `cpu.glb` | PC CPU processor | apleesee | https://sketchfab.com/3d-models/pc-cpu-processor-efb6b95b255c4a37a9661df178ea3bb3 |
| `gpu.glb` | GeForce RTX 3080 Graphics Card | \_surovic\_ | https://sketchfab.com/3d-models/geforce-rtx-3080-graphics-card-8b947ee1bf7a4e3d8ffa1c24893ac160 |
| `motherboard.glb` | Asus Strix b-550-f Gaming Motherboard Realistic | MUSHROOM_BUILDS | https://sketchfab.com/3d-models/asus-strix-b-550-f-gaming-motherboard-realistic-3eba5f45bed74fbeb2647de38047000f |
| `cooler.glb` | Liquid CPU Cooling | Denzerru | https://sketchfab.com/3d-models/liquid-cpu-cooling-7a0014c1141a4c25bc69912075526ee5 |
| `psu.glb` | PSU Power Supply Unit | Groovex | https://sketchfab.com/3d-models/psu-power-supply-unit-69ccd1be3a77497cb2acc9e39e7c52b3 |
| `storage.glb` | M.2 NVME SSD Samsung 990 Pro 1TB | lime.ball.animations | https://sketchfab.com/3d-models/m2-nvme-ssd-samsung-990-pro-1tb-3d-model-41b7bfda7eab40f8b13330913fd66fc2 |
| `ram.glb` | Corsairn VENGEANCE RGB PRO | Nouraiz | https://sketchfab.com/3d-models/corsairn-vengeance-rgb-pro-9b163c4d5ad34edca58488500b5f4daf |

The bottom six URLs were recovered on 2026-08-01 by searching Sketchfab for the
recorded author + title, matching on both.

**Licence verified `CC Attribution` for all eight models.** `gpu.glb`,
`storage.glb` and `ram.glb` were confirmed on 2026-08-01 from the retrieved
listing; `motherboard.glb`, `cooler.glb` and `psu.glb` on 2026-08-02 by opening
their pages in a real browser. Sketchfab renders its licence text client-side,
so `fetch`/curl returns an empty page — those three were unverified for that
reason alone, not because anything looked doubtful. If a model is ever swapped,
verify the replacement the same way: load the page, don't fetch it.

Staged in `/models-staging/`, not yet in use:

| File | Model | Author | Source |
| --- | --- | --- | --- |
| `fan-white.glb` | computer fan | Temoor | https://sketchfab.com/3d-models/computer-fan-5360bd331c5848eeb9338b4f894e78e5 |
| `case.glb` | Fractal Design Meshify C | MUSHROOM_BUILDS | https://sketchfab.com/3d-models/fractal-design-meshify-c-pc-case-a46526af2ac84fa098edc3f01c012450 |

The case is our own procedural geometry, not a downloaded mesh, so it needs no
credit — but do not restate that as "the case *and fans* are ours". The fans are
`fan.glb`, which is somebody else's CC-BY work; the Help page made exactly that
mistake and it took a licence audit to catch.
