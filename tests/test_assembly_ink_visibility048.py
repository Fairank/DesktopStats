"""Complete primary-part ink in actual crowded AIO references; no native GL/UI."""
import copy
from collections import Counter
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QGuiApplication,QOpenGLContext
from PySide6.QtQml import QQmlEngine

import hardware_packs
from assembly_parts import reference_preset
from assembly_profiles import bake_profiles
from assembly_spec import build_spec
from assembly_geometry import Mesh,box,build_scene
from assembly_style import edge_batches,crease_edges,_edge_groups,MAX_STYLE_EDGES
from stats_config import DEFAULT
from tests.test_assembly_ink_priority046 import retained,same_path

STYLES=('outline','notebook_line','sketch')


class AssemblyInkVisibility048Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Software-only geometry construction')
        guards=ExitStack();cls.addClassCleanup(guards.close)
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            guards.enter_context(patch(target,side_effect=AssertionError('No hardware, window or worker')))
        cls.scenes={};cls.lookups={};cls.batches={}
        with tempfile.TemporaryDirectory() as scratch:
            with patch.object(hardware_packs,'_store',hardware_packs.PackStore(Path(scratch)/'packs')):
                engine=QQmlEngine()
                try:
                    preset=reference_preset({},'aio')
                    for identity in dict.fromkeys(('cooler-master-haf-700-evo',preset['case_model'])):
                        config=copy.deepcopy(DEFAULT);config['assembly']=dict(preset,case_model=identity)
                        spec=bake_profiles(build_spec({},config,{},[]),engine)
                        scene=build_scene(dict(spec,visual_style='miniature',part_styles={}))
                        cls.scenes[identity]=scene
                        for style in STYLES:
                            values=edge_batches(scene.meshes,style)
                            cls.batches[identity,style]=values
                            cls.lookups[identity,style]={id(m):data for m,data in values}
                finally:
                    engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        if cls.app.topLevelWindows() or QOpenGLContext.currentContext() is not None:
            raise AssertionError('No window or GL context is permitted')

    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No hardware, window or worker')))

    def each(self):
        for identity,scene in self.scenes.items():
            for style in STYLES:yield identity,style,scene,self.lookups[identity,style]

    def test_each_of_two_real_ram_modules_keeps_entire_pcb_spreader_and_diffuser(self):
        for identity,style,scene,lookup in self.each():
            modules={part:[m for m in scene.meshes if m.part_id==part] for part in ('memory:0','memory:1')}
            for part,meshes in modules.items():
                for name in ('ram-pcb','ram-spreader','ram-diffuser'):
                    with self.subTest(case=identity,style=style,part=part,name=name):
                        mesh=next(m for m in meshes if m.name==name)
                        self.assertTrue(all(retained(edge,lookup.get(id(mesh),())) for edge in crease_edges(mesh.vertices)))

    def test_psu_full_shell_precedes_grille_detail_and_rotating_fan(self):
        for identity,style,scene,lookup in self.each():
            mesh=next(m for m in scene.meshes if m.name=='psu-shell')
            edges=crease_edges(mesh.vertices);self.assertGreater(len(edges),12)
            with self.subTest(case=identity,style=style):
                self.assertTrue(all(retained(edge,lookup.get(id(mesh),())) for edge in edges))
                self.assertTrue(same_path(lookup[id(mesh)],next(v for m,v in edge_batches((mesh,),style) if m is mesh)))

    def test_mainboard_storage_radiator_and_aio_mouth_routes_keep_complete_major_groups(self):
        for identity,style,scene,lookup in self.each():
            for mesh in scene.meshes:
                if mesh.name not in ('motherboard-reference','storage-0-m2-pcb','cooler-liquid-tubes',
                                     'cooler-lfiii-crown-outer-rim','cooler-lfiii-twin-hose-elbows',
                                     'cooler-radiator044-folded-rails'):continue
                with self.subTest(case=identity,style=style,name=mesh.name):
                    data=lookup.get(id(mesh),());edges=crease_edges(mesh.vertices);groups=_edge_groups(edges)
                    maximum=max(span for _,span in groups)
                    if mesh.name in ('cooler-liquid-tubes','cooler-lfiii-crown-outer-rim','cooler-lfiii-twin-hose-elbows'):
                        chosen=range(len(edges))
                    else:chosen=[n for group,span in groups if span>=maximum*.9 for n in group]
                    self.assertTrue(chosen)
                    self.assertTrue(all(retained(edges[n],data) for n in chosen))

    def test_each_main_power_route_keeps_whole_actual_strand_and_both_connector_shells(self):
        for identity,style,scene,lookup in self.each():
            looms=[m for m in scene.meshes if m.component=='cables' and m.name.endswith('-rounded-loom')
                   and any(token in m.name for token in ('-atx24-','-eps8-','-gpu16-'))]
            self.assertEqual(len(looms),4)
            visible_routes=0
            for mesh in looms:
                with self.subTest(case=identity,style=style,route=mesh.name):
                    data=lookup.get(id(mesh),());edges=crease_edges(mesh.vertices);groups=_edge_groups(edges)
                    counts=[sum(retained(edges[n],data) for n in group) for group,_ in groups]
                    visible=any(count==len(group) for count,(group,_) in zip(counts,groups))
                    visible_routes+=int(visible)
                    self.assertTrue(all(count in (0,len(group)) for count,(group,_) in zip(counts,groups)))
                    prefix=mesh.name.removesuffix('-rounded-loom')
                    plugs=[m for m in scene.meshes if m.name.startswith(prefix+'-') and m.name.endswith('-plug-shell')]
                    self.assertEqual(len(plugs),2)
                    for plug in plugs:
                        kept=[retained(e,lookup.get(id(plug),())) for e in crease_edges(plug.vertices)]
                        self.assertTrue(all(kept) if visible else not any(kept))
            self.assertGreaterEqual(visible_routes,1,'Keep a complete main power path, not isolated cable tips')

    def test_main_fan_leaf_and_fixed_frame_groups_are_complete_with_global_and_mesh_caps(self):
        for identity,style,scene,lookup in self.each():
            values=self.batches[identity,style]
            self.assertLessEqual(sum(len(data)//12 for _,data in values),MAX_STYLE_EDGES)
            self.assertLessEqual(max(len(data)//12 for _,data in values),512)
            for mesh in scene.meshes:
                if not (mesh.rotor or mesh.name=='gpu-fan-opening' or mesh.name.endswith('-fan-frame')):continue
                edges=crease_edges(mesh.vertices);groups=_edge_groups(edges);maximum=max(span for _,span in groups)
                threshold=max(maximum*.14,min(12.,maximum*.30)) if mesh.rotor else maximum*.45
                chosen=[n for group,span in groups if span>=threshold for n in group]
                kept=[retained(edges[n],lookup.get(id(mesh),())) for n in chosen]
                with self.subTest(case=identity,style=style,name=mesh.name,part=mesh.part_id):
                    if mesh.name=='cooler-vrm-internal-leaves-hub':
                        self.assertIn(sum(kept),(0,len(kept)))
                    else:self.assertTrue(all(kept))

    def test_isolated_module_and_psu_shell_keep_all_established_edges(self):
        scene=next(iter(self.scenes.values()))
        selected=[m for m in scene.meshes if m.part_id=='memory:0' and m.name!='detail-ram-separated-contacts']
        selected.append(next(m for m in scene.meshes if m.name=='psu-shell'))
        for style in STYLES:
            values={id(m):data for m,data in edge_batches(selected,style)}
            for mesh in selected:self.assertTrue(all(retained(edge,values[id(mesh)]) for edge in crease_edges(mesh.vertices)))

    def test_crowded_actual_m2_cover_removes_t_seams_without_losing_true_creases_or_holes(self):
        import math
        scene=next(iter(self.scenes.values()))
        mesh=max((m for m in scene.meshes if m.name=='detail-board-m2-heatsink'),
                 key=lambda m:len(crease_edges(m.vertices)))
        raw=crease_edges(mesh.vertices)
        self.assertGreater(len(raw),300,'Exercise the actual clipped mounting-hole plate')
        # Independently identify incident non-coplanar triangle faces. Their
        # true bevel/wall creases must survive cancellation of cap partitions.
        normals={}
        for start in range(0,len(mesh.vertices),18):
            row=mesh.vertices[start:start+18]
            points=[tuple(round(v,5) for v in row[n:n+3]) for n in (0,6,12)]
            for a,b in ((0,1),(1,2),(2,0)):
                normals.setdefault(tuple(sorted((points[a],points[b]))),[]).append(row[3:6])
        real=[edge for edge,faces in normals.items() if any(
            -.05<sum(a*b for a,b in zip(faces[0],face))<.8 for face in faces[1:])]
        self.assertGreaterEqual(len(real),10)
        # These are the exact ASUS reference clearances already used by the
        # source model, not three manufacturer-dimensioned M.2 screw holes.
        # The interior one has a front/back loop; the right one meets the edge.
        board=scene.metadata['attachment_anchors']['board']
        self.assertEqual((board['width'],board['height']),(244.,305.))
        radius=3.2;cy=(.5-.538)*board['height']
        left=(.676-.5)*board['width'];right=(.972-.5)*board['width']
        border=(.974-.5)*board['width'];layers=(min(mesh.vertices[0::6]),max(mesh.vertices[0::6]))
        self.assertGreater(border-right,0.);self.assertLess(border-right,radius)
        self.assertAlmostEqual(border-right,.488,places=6)
        # A local segment/triangle calculation checks the actual material,
        # independent of any producer clipping, hole or polygon helper.
        def subtract(a,b):return tuple(a[k]-b[k] for k in range(3))
        def dot(a,b):return sum(a[k]*b[k] for k in range(3))
        def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
        def intersects(a,b):
            direction=subtract(b,a)
            for at in range(0,len(mesh.vertices),18):
                p,q,r=(mesh.vertices[at+k:at+k+3] for k in (0,6,12))
                one,two=subtract(q,p),subtract(r,p);h=cross(direction,two);det=dot(one,h)
                if abs(det)<1e-12:continue
                inv=1./det;s=subtract(a,p);u=dot(s,h)*inv
                if u < -1e-9 or u > 1.+1e-9:continue
                t=cross(s,one);v=dot(direction,t)*inv
                if v < -1e-9 or u+v > 1.+1e-9:continue
                distance=dot(two,t)*inv
                if -1e-9<=distance<=1.+1e-9:return True
            return False
        for center in (left,right):self.assertFalse(intersects((-10.,cy,center),(10.,cy,center)))
        self.assertFalse(intersects((0.,cy,border+4.),(0.,cy,right)),'The edge notch mouth stays open')
        self.assertTrue(intersects((0.,cy+3.7,border+4.),(0.,cy+3.7,border-1.)),'Adjacent material wall stays present')
        self.assertTrue(intersects((-10.,cy,right-3.7),(10.,cy,right-3.7)),'Adjacent cap material stays present')
        # Independent intersections of the reference24-gon with the right
        # edge define both notch mouths. Each cap must keep its arc-to-rim join.
        circle=[(right+radius*math.cos(i*math.tau/24),cy+radius*math.sin(i*math.tau/24)) for i in range(24)]
        mouths=[]
        for a,b in zip(circle,circle[1:]+circle[:1]):
            if (a[0]-border)*(b[0]-border)<0:
                t=(border-a[0])/(b[0]-a[0]);mouths.append(a[1]+t*(b[1]-a[1]))
        self.assertEqual(len(mouths),2)
        def close(a,b):return all(abs(a[k]-b[k])<1e-4 for k in range(3))
        # Dense small contacts create budget pressure without competing for
        # main-cover priority. No physical plate, hole or GPU is rebuilt.
        contact=Mesh('contacts',box(1.,1.,1.),(0.2,0.2,0.2,1.),component='board')
        for style in STYLES:
            isolated=dict((id(m),data) for m,data in edge_batches((mesh,),style))[id(mesh)]
            self.assertTrue(all(retained(edge,isolated) for edge in raw))
            values=edge_batches((mesh,)+(contact,)*700,style)
            data=next(data for m,data in values if m is mesh)
            self.assertTrue(all(retained(edge,data) for edge in real))
            self.assertGreater(sum(not retained(edge,data) for edge in raw),100)
            lines=[(tuple(data[n:n+3]),tuple(data[n+6:n+9])) for n in range(0,len(data),12)]
            holes=[group for group,span in _edge_groups(lines) if 6.3<span<6.5]
            self.assertEqual(len(holes),2,'One interior aperture retains its front/back closed loops; the edge aperture is a notch')
            kept_layers=[]
            for group in holes:
                degrees=Counter(point for n in group for point in lines[n])
                self.assertEqual(set(degrees.values()),{2});self.assertGreaterEqual(len(group),24)
                points=tuple(degrees);layer=min(layers,key=lambda x:abs(points[0][0]-x));kept_layers.append(layer)
                for point in points:
                    self.assertAlmostEqual(point[0],layer,places=4)
                    self.assertAlmostEqual(math.hypot(point[1]-cy,point[2]-left),radius,places=4)
                self.assertAlmostEqual((min(p[1] for p in points)+max(p[1] for p in points))/2,cy,places=4)
                self.assertAlmostEqual((min(p[2] for p in points)+max(p[2] for p in points))/2,left,places=4)
            self.assertEqual(sorted(kept_layers),list(layers))
            notch=[edge for edge in raw if any(abs(edge[0][0]-x)<1e-5 and abs(edge[1][0]-x)<1e-5 for x in layers)
                   and all(radius*math.cos(math.pi/24)-1e-4<=math.hypot(p[1]-cy,p[2]-right)<=radius+1e-4 for p in edge)]
            self.assertGreaterEqual(len(notch),28);self.assertTrue(all(retained(edge,data) for edge in notch))
            for layer in layers:
                for y in mouths:
                    point=(layer,y,border)
                    neighbours=[b if close(a,point) else a for a,b in lines if close(a,point) or close(b,point)]
                    self.assertTrue(any(p[2]<border-1e-5 for p in neighbours),'Notch arc reaches the rim')
                    self.assertTrue(any(abs(p[2]-border)<1e-4 and abs(p[1]-cy)>abs(y-cy)+1e-5 for p in neighbours),'Rim continues outside the notch')
            self.assertLessEqual(sum(len(value)//12 for _,value in values),MAX_STYLE_EDGES)
            self.assertLessEqual(max(len(value)//12 for _,value in values),512)


if __name__=='__main__':unittest.main()
