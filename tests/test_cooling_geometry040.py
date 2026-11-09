"""Independent CPU-only mesh checks for 0.40 cooling reference structures.

No renderer/context, real device, installed Stats process or sampling is used.
Fin samples and unverified contours are illustrations, never factory fin/RPM data.
"""
import copy
import math
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
from assembly_cooling import add_cooling
from assembly_geometry import box, extrude
from assembly_detail import chamfer_rect
from assembly_style import apply_model_styles
from cooling_catalog import get_cooler, get_fan
from top_bar_config import HARDWARE_ICON_STYLES

MODELS=("noctua-nh-l12s","noctua-nh-c14s","bequiet-dark-rock-tf2","zalman-cnps9900-max")
ANCHORS=dict(cpu=dict(position=(0.,0.,0.),normal=(0.,0.,1.),up=(0.,1.,0.)),
             case_dimensions=(600.,800.,800.))


def scene(identity,level="balanced",anchors=None):
    return add_cooling((),dict(cooling=dict(cpu_cooler=identity)),level,anchors or ANCHORS)


def points(mesh):
    return [mesh.vertices[i:i+3] for i in range(0,len(mesh.vertices),6)]


def local(point):
    # This fixture's documented CPU frame has u=+Y, v=-X and n=+Z.
    return point[1],-point[0],point[2]


def bounds(values):
    return tuple((min(p[i] for p in values),max(p[i] for p in values)) for i in range(3))


def chunks(mesh,size):
    return [mesh.vertices[i:i+size] for i in range(0,len(mesh.vertices),size)]


def triangle_hit(vertices,origin,direction):
    def sub(a,b):return tuple(x-y for x,y in zip(a,b))
    def cross(a,b):return a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    for start in range(0,len(vertices),18):
        a,b,c=(vertices[start+i:start+i+3] for i in (0,6,12))
        e1,e2=sub(b,a),sub(c,a);h=cross(direction,e2);det=dot(e1,h)
        if abs(det)<1e-9:continue
        s=sub(origin,a);u=dot(s,h)/det
        if not 0<=u<=1:continue
        q=cross(s,e1);v=dot(direction,q)/det
        if v<0 or u+v>1:continue
        if dot(e2,q)/det>1e-6:return True
    return False


class CoolingGeometry040Tests(unittest.TestCase):
    def test_top_flow_fins_are_vertical_thin_sheets_distributed_across_width(self):
        sheet_size=len(extrude(chamfer_rect(100,30,2),.5))
        for identity in MODELS[:3]:
            banks=2 if identity=="bequiet-dark-rock-tf2" else 1
            for level,count in (("eco",12),("balanced",32),("close",48)):
                meshes,_=scene(identity,level)
                fins=next(mesh for mesh in meshes if mesh.name=="cooler-top-flow-fin-reference")
                plates=chunks(fins,sheet_size)
                self.assertEqual(len(plates),count*banks,(identity,level))
                for start in range(0,len(plates),count):
                    centers=[]
                    for plate in plates[start:start+count]:
                        xyz=[local(plate[i:i+3]) for i in range(0,len(plate),6)]
                        span=bounds(xyz)
                        self.assertAlmostEqual(span[0][1]-span[0][0],.5,places=6)
                        self.assertGreater(span[1][1]-span[1][0],70)
                        self.assertGreater(span[2][1]-span[2][0],20)
                        centers.append(sum(span[0])/2)
                    self.assertEqual(centers,sorted(centers))
                    self.assertGreater(centers[-1]-centers[0],90)

    def test_under_and_above_fan_shells_are_on_the_correct_sides_of_the_bank(self):
        for identity,under in (("noctua-nh-l12s",True),("noctua-nh-c14s",False)):
            meshes,meta=scene(identity)
            fins=next(mesh for mesh in meshes if mesh.name=="cooler-top-flow-fin-reference")
            lo,hi=bounds([local(p) for p in points(fins)])[2]
            fan=meta["fans"][0];model=get_fan(fan["model_id"])
            fan_low=fan["position"][2]-model["depth_mm"]/2
            fan_high=fan["position"][2]+model["depth_mm"]/2
            self.assertEqual(len(meta["fans"]),1)
            self.assertEqual(fan["axis"],(0.,0.,1.))
            if under:
                self.assertLess(fan_high,lo)
                self.assertGreater(fan_low,8)
                self.assertEqual(model["depth_mm"],15)
            else:self.assertGreater(fan_low,hi)
            self.assertLessEqual(fan_high,get_cooler(identity)["dimensions_mm"]["height"])

    def test_tf2_has_one_upper_and_one_interleaved_fan_without_swapping_their_models(self):
        meshes,meta=scene("bequiet-dark-rock-tf2")
        fins=next(mesh for mesh in meshes if mesh.name=="cooler-top-flow-fin-reference")
        sheet_size=len(extrude(chamfer_rect(100,30,2),.5))
        plates=chunks(fins,sheet_size)
        banks=[bounds([local(plate[i:i+3]) for plate in bank for i in range(0,len(plate),6)])[2]
               for bank in (plates[:32],plates[32:])]
        self.assertEqual(len(meta["fans"]),2)
        upper,middle=meta["fans"]
        self.assertEqual([upper["model_id"],middle["model_id"]],get_cooler("bequiet-dark-rock-tf2")["fan_models"])
        upper_model,middle_model=(get_fan(fan["model_id"]) for fan in (upper,middle))
        self.assertEqual((upper_model["depth_mm"],middle_model["depth_mm"]),(25,22))
        self.assertGreater(upper["position"][2]-upper_model["depth_mm"]/2,banks[1][1])
        self.assertGreater(middle["position"][2]-middle_model["depth_mm"]/2,banks[0][1])
        self.assertLess(middle["position"][2]+middle_model["depth_mm"]/2,banks[1][0])

    def test_zalman_has_two_open_radial_banks_and_an_unframed_middle_impeller(self):
        cube_size=len(box(1,1,1))
        for level,count in (("eco",28),("balanced",44),("close",64)):
            meshes,meta=scene("zalman-cnps9900-max",level)
            fins=next(mesh for mesh in meshes if mesh.name=="cooler-radial-tower-fin-reference")
            pieces=chunks(fins,cube_size)
            self.assertEqual(len(pieces),2*count)
            bank_centers=[];bank_radii=[]
            for pieces_bank in (pieces[:count],pieces[count:]):
                centers=[]
                for plate in pieces_bank:
                    span=bounds([local(plate[i:i+3]) for i in range(0,len(plate),6)])
                    centers.append(sum(span[1])/2)
                self.assertLess(max(centers)-min(centers),1e-6)
                bank_centers.append(centers[0])
                center_z=meta["fans"][0]["position"][2]
                bank_radii.append(max(math.hypot(local(plate[i:i+3])[0],local(plate[i:i+3])[2]-center_z)
                    for plate in pieces_bank for i in range(0,len(plate),6)))
            self.assertLess(bank_centers[0],0);self.assertGreater(bank_centers[1],0)
            self.assertLess(bank_radii[0],bank_radii[1],"The front reference bank must be smaller, as in the 2D exterior")
            fan=meta["fans"][0]
            self.assertEqual(local(fan["position"])[1],0)
            self.assertFalse(any("middle-fan-frame" in mesh.name for mesh in meshes))
            self.assertEqual(fan["axis"],(1.,0.,0.))
            self.assertEqual(len([mesh for mesh in meshes if mesh.rotor]),1)
            self.assertFalse(meta["cooler"]["radial_geometry_verified"])
            # A real ray through both central holes must remain unobstructed;
            # a radial ray through a fin still hits the generated metal.
            ring_meshes=[mesh for mesh in meshes if "radial-tower" in mesh.name]
            center_z=fan["position"][2]
            self.assertFalse(any(triangle_hit(mesh.vertices,(-200.,0.,center_z),(1.,0.,0.)) for mesh in ring_meshes))
            self.assertTrue(any(triangle_hit(mesh.vertices,(-200.,50.,center_z),(1.,0.,0.)) for mesh in ring_meshes))

    def test_thirteen_styles_reuse_every_mesh_vertex_axis_and_mechanical_part(self):
        for identity in MODELS:
            meshes,meta=scene(identity)
            for style in HARDWARE_ICON_STYLES:
                styled,policy=apply_model_styles(meshes,style,{},(600.,800.,800.),{"front":"open"})
                self.assertEqual(len(styled),len(meshes))
                self.assertEqual(policy["visual_style"],style)
                for before,after in zip(meshes,styled):
                    self.assertIs(before.vertices,after.vertices)
                    self.assertEqual((before.name,before.position,before.axis,before.rotor,before.direction,before.part_id),
                                     (after.name,after.position,after.axis,after.rotor,after.direction,after.part_id))
            self.assertEqual(len(meta["fans"]),get_cooler(identity)["fan_count"])

    def test_rpm_and_absolute_direction_are_never_fabricated_by_geometry(self):
        for identity in (*MODELS,"scythe-fuma3"):
            _,meta=scene(identity)
            self.assertFalse(meta["automatic_detection"])
            self.assertEqual(meta["new_pollers"],0)
            self.assertEqual(meta["default_fan_motion"],"static_without_fresh_group_tach")
            for fan in meta["fans"]:
                self.assertIsNone(fan["rpm"])
                self.assertEqual(fan["rotation_default"],"static")
                self.assertFalse(fan["rotation_direction_verified"])
            if identity=="zalman-cnps9900-max":
                self.assertFalse(meta["fans"][0]["blade_count_verified"])
                self.assertEqual(meta["real_cpu_rotor_parts"],[])

    def test_fuma_relative_counter_rotation_keeps_common_axis_and_distinct_impellers(self):
        meshes,meta=scene("scythe-fuma3")
        rotors=[mesh for mesh in meshes if mesh.rotor]
        self.assertEqual(len(rotors),2)
        self.assertEqual([mesh.direction for mesh in rotors],[1,-1])
        self.assertEqual(rotors[0].axis,rotors[1].axis)
        self.assertEqual([fan["model_id"] for fan in meta["fans"]],get_cooler("scythe-fuma3")["fan_models"])
        fan_models=[get_fan(fan["model_id"]) for fan in meta["fans"]]
        self.assertEqual([(fan["depth_mm"],fan["blades"]) for fan in fan_models],[(15,11),(26,9)])
        self.assertTrue(meta["cooler"]["relative_rotation_verified"])

    def test_mesh_normals_and_detail_buffers_stay_finite_and_bounded_without_io(self):
        original=copy.deepcopy(ANCHORS)
        for identity in MODELS:
            counts=[]
            for level in ("eco","balanced","close"):
                with patch("ctypes.WinDLL",side_effect=AssertionError("No native API")), \
                     patch("subprocess.Popen",side_effect=AssertionError("No process")), \
                     patch("threading.Thread.start",side_effect=AssertionError("No worker")):
                    meshes,meta=scene(identity,level)
                triangles=sum(len(mesh.vertices)//18 for mesh in meshes)
                counts.append(triangles)
                self.assertLess(triangles,12000)
                self.assertLess(sum(len(mesh.vertices)*4 for mesh in meshes),1_000_000)
                for mesh in meshes:
                    self.assertEqual(len(mesh.vertices)%18,0)
                    self.assertTrue(all(math.isfinite(v) for v in mesh.vertices))
                    for start in range(0,len(mesh.vertices),6):
                        self.assertAlmostEqual(sum(mesh.vertices[start+i]**2 for i in (3,4,5)),1.,places=5)
                self.assertFalse(meta["rejected"])
            self.assertEqual(counts,sorted(counts))
        self.assertEqual(ANCHORS,original)


if __name__=="__main__":unittest.main()
