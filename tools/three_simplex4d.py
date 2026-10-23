"""Dependency-free 4D-only Python port of three.js r150 SimplexNoise.

Original source notice (retained verbatim):
    Ported from Stefan Gustavson's java implementation
    http://staffwww.itn.liu.se/~stegu/simplexnoise/simplexnoise.pdf
    Read Stefan's excellent paper for details on how this code works.

    Sean McCullough banksean@gmail.com

    Added 4D noise

Reference source:
https://github.com/mrdoob/three.js/blob/r150/examples/jsm/math/SimplexNoise.js
MIT license:
https://github.com/mrdoob/three.js/blob/r150/LICENSE

The MIT License

Copyright © 2010-2023 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

This port keeps the source's strict comparisons, gradient/lookup tables,
operation order, 256 random-byte draws (including duplicates), doubled table,
and factor 27. Only the parts needed by noise4d are included. The source calls
its lookup table ``simplex``; ``simplexLookup`` is a descriptive alias here.
The seed uses a private Python random.Random, not JavaScript Math.random;
cross-language comparisons therefore inject the same explicit 256-item table.
This is a numerical reference for offline artwork, not visual acceptance.
"""

import math
import random

_GRAD4 = (
    (0, 1, 1, 1), (0, 1, 1, -1), (0, 1, -1, 1), (0, 1, -1, -1),
    (0, -1, 1, 1), (0, -1, 1, -1), (0, -1, -1, 1), (0, -1, -1, -1),
    (1, 0, 1, 1), (1, 0, 1, -1), (1, 0, -1, 1), (1, 0, -1, -1),
    (-1, 0, 1, 1), (-1, 0, 1, -1), (-1, 0, -1, 1), (-1, 0, -1, -1),
    (1, 1, 0, 1), (1, 1, 0, -1), (1, -1, 0, 1), (1, -1, 0, -1),
    (-1, 1, 0, 1), (-1, 1, 0, -1), (-1, -1, 0, 1), (-1, -1, 0, -1),
    (1, 1, 1, 0), (1, 1, -1, 0), (1, -1, 1, 0), (1, -1, -1, 0),
    (-1, 1, 1, 0), (-1, 1, -1, 0), (-1, -1, 1, 0), (-1, -1, -1, 0),
)

_SIMPLEX_LOOKUP = (
    (0, 1, 2, 3), (0, 1, 3, 2), (0, 0, 0, 0), (0, 2, 3, 1), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (1, 2, 3, 0),
    (0, 2, 1, 3), (0, 0, 0, 0), (0, 3, 1, 2), (0, 3, 2, 1), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (1, 3, 2, 0),
    (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0),
    (1, 2, 0, 3), (0, 0, 0, 0), (1, 3, 0, 2), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (2, 3, 0, 1), (2, 3, 1, 0),
    (1, 0, 2, 3), (1, 0, 3, 2), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (2, 0, 3, 1), (0, 0, 0, 0), (2, 1, 3, 0),
    (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0),
    (2, 0, 1, 3), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (3, 0, 1, 2), (3, 0, 2, 1), (0, 0, 0, 0), (3, 1, 2, 0),
    (2, 1, 0, 3), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (3, 1, 0, 2), (0, 0, 0, 0), (3, 2, 0, 1), (3, 2, 1, 0),
)

_F4 = (math.sqrt(5.0) - 1.0) / 4.0
_G4 = (5.0 - math.sqrt(5.0)) / 20.0


class SimplexNoise:
    """4D subset of the original class, with reproducible table injection.

    ``SimplexNoise(seed=39)`` owns an independent seeded generator.
    ``SimplexNoise(permutation=table)`` accepts exactly 256 integer bytes;
    duplicates are intentional and valid, matching the original constructor.
    ``SimplexNoise(random_source=r)`` accepts an object with ``random()`` or a
    callable returning a finite float in [0, 1). Specify only one input mode.
    The unseeded default also owns an independent generator.
    """

    def __init__(self, random_source=None, *, seed=None, permutation=None):
        if sum(value is not None for value in (random_source, seed, permutation)) > 1:
            raise ValueError("Specify only one of random_source, seed, or permutation")
        self.grad4 = _GRAD4
        self.simplexLookup = _SIMPLEX_LOOKUP
        self.simplex = self.simplexLookup
        if permutation is not None:
            self.p = list(permutation)
            if len(self.p) != 256 or any(type(value) is not int or not 0 <= value <= 255 for value in self.p):
                raise ValueError("permutation must contain exactly 256 integer bytes (duplicates allowed)")
        else:
            source = random.Random(seed) if random_source is None else random_source
            random_fn = source.random if hasattr(source, "random") else source
            self.p = []
            for _ in range(256):
                value = random_fn()
                if not math.isfinite(value) or not 0 <= value < 1:
                    raise ValueError("random_source must return finite numbers in [0, 1)")
                self.p.append(math.floor(value * 256))
        # Remove the need for index wrapping by doubling the original table.
        self.perm = [self.p[index & 255] for index in range(512)]

    @staticmethod
    def dot4(g, x, y, z, w):
        return g[0] * x + g[1] * y + g[2] * z + g[3] * w

    def noise4d(self, x, y, z, w):
        """Evaluate the original 4D simplex formula at finite coordinates."""
        x, y, z, w = float(x), float(y), float(z), float(w)
        grad4 = self.grad4
        simplex = self.simplex
        perm = self.perm
        F4 = _F4
        G4 = _G4
        s = (x + y + z + w) * F4
        i = math.floor(x + s)
        j = math.floor(y + s)
        k = math.floor(z + s)
        l = math.floor(w + s)  # noqa: E741 - retain the upstream mathematical variable.
        t = (i + j + k + l) * G4
        X0 = i - t
        Y0 = j - t
        Z0 = k - t
        W0 = l - t
        x0 = x - X0
        y0 = y - Y0
        z0 = z - Z0
        w0 = w - W0

        # Six strict pair comparisons select the original simplex traversal.
        c1 = 32 if x0 > y0 else 0
        c2 = 16 if x0 > z0 else 0
        c3 = 8 if y0 > z0 else 0
        c4 = 4 if x0 > w0 else 0
        c5 = 2 if y0 > w0 else 0
        c6 = 1 if z0 > w0 else 0
        c = c1 + c2 + c3 + c4 + c5 + c6
        i1 = 1 if simplex[c][0] >= 3 else 0
        j1 = 1 if simplex[c][1] >= 3 else 0
        k1 = 1 if simplex[c][2] >= 3 else 0
        l1 = 1 if simplex[c][3] >= 3 else 0
        i2 = 1 if simplex[c][0] >= 2 else 0
        j2 = 1 if simplex[c][1] >= 2 else 0
        k2 = 1 if simplex[c][2] >= 2 else 0
        l2 = 1 if simplex[c][3] >= 2 else 0
        i3 = 1 if simplex[c][0] >= 1 else 0
        j3 = 1 if simplex[c][1] >= 1 else 0
        k3 = 1 if simplex[c][2] >= 1 else 0
        l3 = 1 if simplex[c][3] >= 1 else 0
        x1 = x0 - i1 + G4
        y1 = y0 - j1 + G4
        z1 = z0 - k1 + G4
        w1 = w0 - l1 + G4
        x2 = x0 - i2 + 2.0 * G4
        y2 = y0 - j2 + 2.0 * G4
        z2 = z0 - k2 + 2.0 * G4
        w2 = w0 - l2 + 2.0 * G4
        x3 = x0 - i3 + 3.0 * G4
        y3 = y0 - j3 + 3.0 * G4
        z3 = z0 - k3 + 3.0 * G4
        w3 = w0 - l3 + 3.0 * G4
        x4 = x0 - 1.0 + 4.0 * G4
        y4 = y0 - 1.0 + 4.0 * G4
        z4 = z0 - 1.0 + 4.0 * G4
        w4 = w0 - 1.0 + 4.0 * G4
        ii = i & 255
        jj = j & 255
        kk = k & 255
        ll = l & 255
        gi0 = perm[ii + perm[jj + perm[kk + perm[ll]]]] % 32
        gi1 = perm[ii + i1 + perm[jj + j1 + perm[kk + k1 + perm[ll + l1]]]] % 32
        gi2 = perm[ii + i2 + perm[jj + j2 + perm[kk + k2 + perm[ll + l2]]]] % 32
        gi3 = perm[ii + i3 + perm[jj + j3 + perm[kk + k3 + perm[ll + l3]]]] % 32
        gi4 = perm[ii + 1 + perm[jj + 1 + perm[kk + 1 + perm[ll + 1]]]] % 32

        t0 = 0.6 - x0 * x0 - y0 * y0 - z0 * z0 - w0 * w0
        if t0 < 0:
            n0 = 0.0
        else:
            t0 *= t0
            n0 = t0 * t0 * self.dot4(grad4[gi0], x0, y0, z0, w0)
        t1 = 0.6 - x1 * x1 - y1 * y1 - z1 * z1 - w1 * w1
        if t1 < 0:
            n1 = 0.0
        else:
            t1 *= t1
            n1 = t1 * t1 * self.dot4(grad4[gi1], x1, y1, z1, w1)
        t2 = 0.6 - x2 * x2 - y2 * y2 - z2 * z2 - w2 * w2
        if t2 < 0:
            n2 = 0.0
        else:
            t2 *= t2
            n2 = t2 * t2 * self.dot4(grad4[gi2], x2, y2, z2, w2)
        t3 = 0.6 - x3 * x3 - y3 * y3 - z3 * z3 - w3 * w3
        if t3 < 0:
            n3 = 0.0
        else:
            t3 *= t3
            n3 = t3 * t3 * self.dot4(grad4[gi3], x3, y3, z3, w3)
        t4 = 0.6 - x4 * x4 - y4 * y4 - z4 * z4 - w4 * w4
        if t4 < 0:
            n4 = 0.0
        else:
            t4 *= t4
            n4 = t4 * t4 * self.dot4(grad4[gi4], x4, y4, z4, w4)
        return 27.0 * (n0 + n1 + n2 + n3 + n4)


SimplexNoise4D = SimplexNoise

__all__ = ["SimplexNoise", "SimplexNoise4D"]
