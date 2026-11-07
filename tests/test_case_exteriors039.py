"""Pure bounded geometry checks; no renderer, GUI, sensors or network."""
import math
import unittest

from assembly_case_exteriors import replace_shell
from assembly_geometry import Mesh, box
from chassis_catalog_group_d import records
import chassis_catalog as catalog


def _records():
    return {row["id"]: row for row in records(catalog._case, catalog._mount,
                                              catalog._ATX, catalog._EATX)}


def _dimensions(case):
    return tuple(case["dimensions_mm"][key] for key in ("width", "height", "depth"))


def _bounds(meshes):
    return tuple((min(mesh.vertices[index] + mesh.position[axis]
                      for mesh in meshes for index in range(axis, len(mesh.vertices), 6)),
                  max(mesh.vertices[index] + mesh.position[axis]
                      for mesh in meshes for index in range(axis, len(mesh.vertices), 6)))
                 for axis in range(3))


class CaseExteriors039Tests(unittest.TestCase):
    def test_old_64_have_exact_identity_and_no_extra_geometry(self):
        source = (Mesh("case-back", box(2, 3, 4), (.3, .4, .5, 1)),)
        for case in catalog.CASES[:64]:
            self.assertIs(replace_shell(source, _dimensions(case), case), source)

    def test_full_shell_replacement_keeps_hardware_objects_and_removes_generic_walls(self):
        hardware = Mesh("motherboard-pcb", box(1, 2, 3), (.2, .5, .3, 1), component="motherboard")
        source = (Mesh("case-back", box(3, 4, 2), (.3, .4, .5, 1)), hardware,
                  Mesh("left-glass", box(1, 4, 3), (.3, .4, .5, .15), component="panel"))
        for case_id in ("streacom-da6", "streacom-bc1-v2", "streacom-db4", "fractal-mood"):
            case = _records()[case_id]
            result = replace_shell(source, _dimensions(case), case)
            self.assertIs(result[0], hardware)
            self.assertFalse(any(mesh.name in ("case-back", "left-glass") for mesh in result))
            self.assertEqual(sum(mesh.component not in ("case", "panel") for mesh in result), 1)

    def test_each_detail_level_has_finite_unit_normals_and_bounded_batches(self):
        for case in _records().values():
            for level, cap in (("eco", 4000), ("balanced", 6500), ("close", 11000)):
                result = replace_shell((), _dimensions(case), case, level)
                with self.subTest(case=case["id"], level=level):
                    self.assertLessEqual(len(result), 8)
                    self.assertLess(sum(mesh.vertex_count // 3 for mesh in result), cap)
                    for mesh in result:
                        self.assertEqual(len(mesh.vertices) % 18, 0)
                        self.assertTrue(all(math.isfinite(v) for v in mesh.vertices))
                        for offset in range(0, len(mesh.vertices), 6):
                            self.assertAlmostEqual(sum(v * v for v in mesh.vertices[offset + 3:offset + 6]), 1., places=6)
                        self.assertFalse(mesh.rotor)
                        self.assertIn(mesh.component, ("case", "panel"))

    def test_catalog_axes_are_preserved_in_the_four_distinct_shells(self):
        for case_id in ("streacom-da6", "streacom-bc1-v2", "streacom-db4", "fractal-mood"):
            case = _records()[case_id]
            expected = _dimensions(case)
            result = replace_shell((), expected, case, "close")
            for (minimum, maximum), dimension in zip(_bounds(result), expected):
                # BC1 support pins intentionally rise 8 mm above the empty rack.
                allowance = 8.01 if case_id == "streacom-bc1-v2" else .6
                self.assertGreaterEqual(minimum, -dimension / 2 - .6)
                self.assertLessEqual(maximum, dimension / 2 + allowance)
                self.assertAlmostEqual(minimum, -dimension / 2, delta=1.)
                self.assertAlmostEqual(maximum, dimension / 2 + (8. if case_id == "streacom-bc1-v2" and dimension == 115 else 0), delta=1.)

    def test_da6_is_a_round_tube_open_frame_without_large_opaque_walls(self):
        case = _records()["streacom-da6"]
        result = replace_shell((), _dimensions(case), case, "close")
        self.assertEqual(len(result), 3)
        self.assertTrue(any("tubular-metal-frame" in mesh.name for mesh in result))
        for mesh in result:
            for offset in range(0, len(mesh.vertices), 18):
                a, b, c = (mesh.vertices[offset + n:offset + n + 3] for n in (0, 6, 12))
                u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
                cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
                self.assertLess(math.sqrt(sum(x*x for x in cross)) / 2., 1400.)

    def test_bench_platform_and_pin_top_follow_the_empty_rack_height(self):
        case = _records()["streacom-bc1-v2"]
        result = replace_shell((), _dimensions(case), case)
        platform = tuple(mesh for mesh in result if "platform" in mesh.name)
        pins = tuple(mesh for mesh in result if "standoffs" in mesh.name)
        self.assertEqual(_bounds(platform)[1], (49.5, 57.5))
        self.assertEqual(_bounds(pins)[1], (57.5, 65.5))
        self.assertFalse(any("back" in mesh.name for mesh in result))

    def test_cooling_cube_fabric_column_and_table_have_distinct_material_structures(self):
        names = {}
        for case_id in ("streacom-db4", "fractal-mood", "streacom-bc1-v2"):
            case = _records()[case_id]
            names[case_id] = {mesh.name for mesh in replace_shell((), _dimensions(case), case)}
        self.assertTrue(any("fins" in name for name in names["streacom-db4"]))
        self.assertTrue(any("fabric" in name for name in names["fractal-mood"]))
        self.assertTrue(any("platform" in name for name in names["streacom-bc1-v2"]))
        self.assertTrue(names["streacom-db4"].isdisjoint(names["fractal-mood"]))

    def test_empty_front_gpu_chamber_does_not_create_installed_devices(self):
        case = _records()["lian-li-sup01"]
        original = Mesh("case-back", box(2, 3, 4), (.2, .3, .4, 1))
        result = replace_shell((original,), _dimensions(case), case)
        self.assertIs(result[0], original)
        self.assertTrue(any("front-gpu-reference" in mesh.name for mesh in result))
        self.assertTrue(all(mesh.component == "case" for mesh in result))
        self.assertFalse(any(mesh.rotor for mesh in result))


if __name__ == "__main__":
    unittest.main()
