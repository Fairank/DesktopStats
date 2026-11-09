"""Exact-SKU observed exteriors; unknown blades stay still and unknown."""
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')

from assembly_gpu_legacy052 import EXACT_ID,MANUAL_ID,METAL_COVER,refine,side_windows
from assembly_style import apply_model_styles,edge_batches,material_for
from hardware_fan_profiles import PROFILES,profile_for
from hardware_appearance import CATALOG,appearance_for

ROOT=Path(__file__).resolve().parents[1]
SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def hits_segment(mesh,a,b):
    delta=tuple(b[k]-a[k] for k in range(3));origin=tuple(a[k]-mesh.position[k] for k in range(3));v=mesh.vertices
    for n in range(0,len(v),18):
        p,q,r=(v[n+i:n+i+3] for i in (0,6,12));u=tuple(q[k]-p[k] for k in range(3));w=tuple(r[k]-p[k] for k in range(3));h=cross(delta,w);d=dot(u,h)
        if abs(d)<1e-10:continue
        inv=1/d;s=tuple(origin[k]-p[k] for k in range(3));x=inv*dot(s,h)
        if x<0 or x>1:continue
        j=cross(s,u);y=inv*dot(delta,j)
        if y<0 or x+y>1:continue
        t=inv*dot(w,j)
        if 0<t<1:return True
    return False


class ExactEvidenceData052Tests(unittest.TestCase):
    def test_metal_caps_do_not_turn_unreviewed_acer_or_fx_blades_into_known_rotors(self):
        acer=PROFILES['acer_bifrost_arc_a770'];self.assertEqual(acer['model_ids'],('acer-bifrost-a770-16g-oc',))
        self.assertEqual([row['hub_tone'] for row in acer['fans']],['silver','silver'])
        self.assertEqual([row['blades'] for row in acer['fans']],[None,None])
        self.assertTrue(all(row['shape']=='neutral' for row in acer['fans']))
        self.assertEqual(PROFILES['gigabyte_fx5200']['hub_tone'],'light')
        self.assertIsNone(PROFILES['gigabyte_fx5200']['blades'])
        for identity in ('acer-bifrost-a770-16g-oc','gigabyte-fx5200-n52128d',EXACT_ID):
            row=next(row for row in CATALOG if row[0]==identity)
            appearance=appearance_for('gpu',row[-1][0]);self.assertFalse(profile_for(appearance)['render_ready'])
            self.assertEqual(profile_for(dict(appearance,id='unreviewed-similar-sku')), {})

    def test_generated_native_data_is_the_actual_python_profile_payload(self):
        from tools.generate_hardware_fan_data import payload
        text=(ROOT/'native/HardwareFanProfileData.js').read_text(encoding='utf8')
        self.assertEqual(json.loads(text.split('var profiles = ',1)[1]),payload())
        from hardware_board_details import drawing_payload
        text=(ROOT/'native/HardwareBoardProfileData.js').read_text(encoding='utf8')
        self.assertEqual(json.loads(text.split('var models = ',1)[1]),drawing_payload())

    def test_seven_blade_revision_requires_explicit_manual_reference_identity(self):
        base=appearance_for('gpu','GV-N52128D')
        self.assertEqual(base['id'],'gigabyte-fx5200-n52128d');self.assertFalse(profile_for(base)['render_ready'])
        for alias in ('GV-N52128D Rev. 1.0 Manual Reference','GV-N52128D Rev.1.0 手册参考'):
            reviewed=appearance_for('gpu',alias);self.assertEqual(reviewed['id'],MANUAL_ID)
            self.assertTrue(profile_for(reviewed)['render_ready']);self.assertEqual(profile_for(reviewed)['blades'],7)
            self.assertEqual(reviewed['board_details']['fan_profile']['hub_tone'],'dark')
            self.assertEqual(reviewed['board_details']['edge_key_count'],2)
            self.assertTrue(all(v is None for v in reviewed['board_details']['dimensions_mm'].values()))
        for alias in ('GV-N52128D Rev.1.0','NVIDIA GeForce FX 5200','GV-N52128T-P','GV-N52128D Rev.2.0 Manual Reference'):
            self.assertNotEqual(appearance_for('gpu',alias)['id'],MANUAL_ID)

    def test_exact_helper_cannot_change_astral_other_skus_or_invent_backside_routes(self):
        sentinel=();self.assertIs(refine(sentinel,{'gpu':{'appearance':{'id':'asus-astral-5090'}}},'close')[0],sentinel)
        self.assertEqual(side_windows('msi-n260gtx-lightning-black-edition',(),100,32),{})


class ActualEvidenceGeometry052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtQml import QQmlEngine
        from assembly_profiles import bake_profiles
        cls.app=QCoreApplication.instance()or QCoreApplication([]);cls.engine=QQmlEngine();cls.specs={}
        for identity in (EXACT_ID,'acer-bifrost-a770-16g-oc','gigabyte-fx5200-n52128d',MANUAL_ID):
            row=next(row for row in CATALOG if row[0]==identity);a=appearance_for('gpu',row[-1][0]);d=a['board_details'].get('dimensions_mm')or{}
            cls.specs[identity]=bake_profiles(dict(case={'layout':'tower'},visual_style='miniature',
                cpu={'appearance':appearance_for('cpu','Intel Core i7-13700KF')},memory={'count':0,'modules':[]},
                gpu=dict(appearance=a,length_mm=d.get('length') or 270.,width_mm=d.get('height') or 130.,thickness_mm=d.get('thickness') or 45.)),cls.engine)
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        cls.component=QQmlComponent(cls.engine)
        cls.component.setData(b'import QtQml\nimport "HardwareShapes.js" as Shapes\nQtObject {function art(a,s){a.icon_set=s;a.model_mode=true;return Shapes.source(Shapes.key(a,"#455360"))}}',
                              QUrl.fromLocalFile(str(ROOT/'native/FXEvidenceBridge052.qml')))
        cls.source_object=cls.component.create();assert cls.source_object is not None

    @classmethod
    def tearDownClass(cls):
        from PySide6.QtCore import QCoreApplication,QEvent
        cls.source_object.deleteLater();cls.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No hardware/network/window/worker')))

    def test_actual_legacy_three_lods_keep_face_holes_envelope_and_real_finite_pipe_surfaces(self):
        from assembly_geometry import build_scene
        for level in ('eco','balanced','close'):
            spec=dict(self.specs[EXACT_ID],detail_level=level)
            current=build_scene(spec)
            with patch('assembly_gpu_legacy052.refine',side_effect=lambda meshes,*args:(meshes,{})),patch('assembly_gpu_legacy052.side_windows',return_value={}):
                previous=build_scene(spec)
            before=[m for m in previous.meshes if m.name=='gpu-cover-panel'];after=[m for m in current.meshes if m.name==METAL_COVER]
            self.assertGreater(len(after),0);self.assertEqual(len(before),len(after))
            for a,b in zip(before,after):
                self.assertEqual((a.vertices,a.position,a.color,a.axis,a.rotor),(b.vertices,b.position,b.color,b.axis,b.rotor))
            shell=next(m for m in current.meshes if m.name=='gpu-shroud');old=next(m for m in previous.meshes if m.name=='gpu-shroud')
            low=[min(shell.vertices[k::6]) for k in range(3)];high=[max(shell.vertices[k::6]) for k in range(3)]
            self.assertEqual((low,high),([min(old.vertices[k::6]) for k in range(3)],[max(old.vertices[k::6]) for k in range(3)]))
            gx,gy,gz=shell.position
            # gpu_plane maps source local-Y negative to actual+X. Only this
            # photo-observed long edge opens; the opposite wall stays intact.
            ray_a=(gx+high[0]+1,gy,gz);ray_b=(gx+high[0]-3,gy,gz)
            self.assertTrue(hits_segment(old,ray_a,ray_b));self.assertFalse(hits_segment(shell,ray_a,ray_b))
            self.assertTrue(hits_segment(shell,(gx+low[0]-1,gy,gz),(gx+low[0]+3,gy,gz)))
            pipe=next(m for m in current.meshes if m.name=='detail-gpu-lightning-visible-metal-pipe-bends')
            self.assertFalse(pipe.rotor);self.assertLessEqual(current.triangle_count-previous.triangle_count,1500)
            fins=next(m for m in current.meshes if m.name=='detail-gpu-lightning-observed-sampled-fin-stack')
            self.assertFalse(fins.rotor)
            for k in range(3):
                self.assertGreaterEqual(min(fins.vertices[k::6]),low[k]-1e-7)
                self.assertLessEqual(max(fins.vertices[k::6]),high[k]+1e-7)
            for k in range(3):
                self.assertGreaterEqual(min(pipe.vertices[k::6]),low[k]-1e-7);self.assertLessEqual(max(pipe.vertices[k::6]),high[k]+1e-7)
            for n in range(0,len(pipe.vertices),6):self.assertAlmostEqual(math.hypot(*pipe.vertices[n+3:n+6]),1.,places=7)
            for n in range(0,len(pipe.vertices),18):
                a,b,c=(pipe.vertices[n+j:n+j+3] for j in (0,6,12));u=tuple(b[k]-a[k] for k in range(3));v=tuple(c[k]-a[k] for k in range(3));face=cross(u,v)
                average=tuple(sum(pipe.vertices[n+j+3+k] for j in (0,6,12)) for k in range(3))
                self.assertGreater(dot(face,face),1e-14);self.assertGreater(dot(face,average),0)
            metadata=current.metadata['detail']['gpu']
            self.assertEqual(metadata['documented_total_heatpipes'],5);self.assertEqual(metadata['observed_reference_visible_pipe_bends'],2)
            self.assertTrue(metadata['fan_blade_count_still_unverified']);self.assertFalse(metadata['heatpipe_diameter_verified'])

    def test_exact_metal_cover_keeps_all_six_physical_arrays_and_real_partition_ink(self):
        from assembly_geometry import build_scene
        scene=build_scene(self.specs[EXACT_ID]);meshes=tuple(m for m in scene.meshes if m.component=='gpu')
        cover=next(m for m in meshes if m.name==METAL_COVER)
        self.assertGreater(material_for(cover,'miniature')[0],material_for(replace(cover,name='gpu-cover-panel'),'miniature')[0])
        for style in SIX:
            values,meta=apply_model_styles(meshes,style,{},scene.dimensions,{'front':'open'})
            self.assertTrue(all(a.vertices is b.vertices for a,b in zip(values,meshes)))
            self.assertLessEqual(sum(len(v)//12 for _,v in edge_batches(values,style,meta['mesh_style_ids'])),8192)
            actual=edge_batches((cover,),style);legacy=edge_batches((replace(cover,name='gpu-cover-panel'),),style)
            self.assertEqual([v for _,v in actual],[v for _,v in legacy])

    def test_native_profile_and_actual_three_dimensional_hubs_use_reviewed_cap_colors_only(self):
        from assembly_geometry import build_scene
        expected={'acer-bifrost-a770-16g-oc':(189/255,201/255,208/255,1.),'gigabyte-fx5200-n52128d':(225/255,230/255,232/255,1.)}
        for identity,tone in expected.items():
            scene=build_scene(self.specs[identity]);hubs=[m for m in scene.meshes if m.name=='gpu-fan-hub']
            self.assertEqual(len(hubs),2 if identity.startswith('acer')else 1)
            for hub in hubs:self.assertEqual(hub.color,tone)
            self.assertFalse(any(m.name=='gpu-fan-rotor' and m.rotor for m in scene.meshes))

    def test_exact_fx5200_exposes_native_blue_board_without_modern_shroud_and_preserves_io_agp(self):
        from assembly_geometry import build_scene
        identity='gigabyte-fx5200-n52128d'
        self.assertEqual(self.specs[identity]['gpu']['colors']['pcb'],'#386e98')
        for level in ('eco','balanced','close'):
            spec=dict(self.specs[identity],detail_level=level);scene=build_scene(spec)
            with patch('assembly_gpu_legacy052.refine',side_effect=lambda meshes,*args:(meshes,{})):
                old=build_scene(spec)
            gpu=tuple(m for m in scene.meshes if m.component=='gpu')
            self.assertFalse(any(m.name in ('gpu-shroud','gpu-cover-panel') for m in gpu))
            pcb=next(m for m in gpu if m.name=='gpu-pcb');old_pcb=next(m for m in old.meshes if m.name=='gpu-pcb')
            self.assertEqual(pcb.color,(56/255,110/255,152/255,1.))
            self.assertEqual([m.name for m in gpu if m.name.startswith('gpu-reference-port-')],
                             ['gpu-reference-port-dvi','gpu-reference-port-tv_out','gpu-reference-port-vga'])
            self.assertEqual(len([m for m in gpu if m.name.startswith('detail-gpu-fx5200-observed-memory-package-')]),8)
            self.assertEqual(len([m for m in gpu if m.name.startswith('detail-gpu-fx5200-observed-capacitor-body-')]),6)
            opening=next(m for m in gpu if m.name=='gpu-fan-opening')
            memory=[m for m in gpu if m.name.startswith('detail-gpu-fx5200-observed-memory-package-')]
            self.assertTrue(all(m.position[0]<opening.position[0]-20 for m in memory[:4]))
            self.assertTrue(all((max(m.vertices[0::6])-min(m.vertices[0::6]))>(max(m.vertices[2::6])-min(m.vertices[2::6])) for m in memory[:4]))
            self.assertTrue(all((max(m.vertices[2::6])-min(m.vertices[2::6]))>(max(m.vertices[0::6])-min(m.vertices[0::6])) for m in memory[4:]))
            self.assertEqual(sum(m.position[2]>opening.position[2]+70 for m in memory),4)
            tongue=[m for m in gpu if m.name.startswith('detail-gpu-fx5200-observed-agp-tongue-')]
            self.assertEqual(len(tongue),3)
            intervals=sorted((min(m.vertices[2::6])+m.position[2],max(m.vertices[2::6])+m.position[2]) for m in tongue)
            self.assertTrue(all(a[1]<b[0] for a,b in zip(intervals,intervals[1:])))
            p0=min(pcb.vertices[2::6])+pcb.position[2];span=max(pcb.vertices[2::6])-min(pcb.vertices[2::6])
            for interval,expected in zip(intervals,((.385,.525),(.535,.647),(.658,.800))):
                for actual,want in zip(interval,expected):self.assertAlmostEqual((actual-p0)/span,want,places=7)
            self.assertTrue(any(m.name=='detail-gpu-fx5200-vga-fifteen-reference-contacts' for m in gpu))
            sink=next(m for m in gpu if m.name=='detail-gpu-fx5200-black-radial-heatsink')
            self.assertFalse(sink.rotor);self.assertLessEqual(sink.vertex_count//3,700)
            for k in (0,2):
                self.assertGreaterEqual(min(sink.vertices[k::6])+sink.position[k],min(pcb.vertices[k::6])+pcb.position[k])
                self.assertLessEqual(max(sink.vertices[k::6])+sink.position[k],max(pcb.vertices[k::6])+pcb.position[k])
            for n in range(0,len(sink.vertices),18):
                a,b,c=(sink.vertices[n+j:n+j+3] for j in (0,6,12));normal=cross(tuple(b[k]-a[k] for k in range(3)),tuple(c[k]-a[k] for k in range(3)))
                self.assertGreater(dot(normal,normal),1e-16)
                self.assertGreater(dot(normal,sink.vertices[n+3:n+6]),0)
            self.assertLessEqual(scene.triangle_count-old.triangle_count,3000)
            meta=scene.metadata['detail']['gpu'];self.assertFalse(meta['actual_card_dimensions_verified'])
            self.assertTrue(meta['heatsink_fin_count_is_sampling']);self.assertTrue(meta['fan_blade_count_still_unverified'])
            for style in SIX:
                values,info=apply_model_styles(gpu,style,{},scene.dimensions,{'front':'open'})
                self.assertTrue(all(a.vertices is b.vertices for a,b in zip(values,gpu)))
                self.assertLessEqual(sum(len(v)//12 for _,v in edge_batches(values,style,info['mesh_style_ids'])),8192)

    def test_manual_revision_native_rotor_keeps_seven_real_curved_leaves_without_promoting_base(self):
        from assembly_geometry import build_scene
        spec=self.specs[MANUAL_ID];self.assertEqual(spec['gpu']['fans'][0]['blades'],7)
        self.assertEqual(len(spec['gpu']['fans'][0]['blade_polygons']),7)
        for level in ('eco','balanced','close'):
            scene=build_scene(dict(spec,detail_level=level));rotor=next(m for m in scene.meshes if m.name=='gpu-fan-rotor')
            self.assertTrue(rotor.rotor);self.assertGreater(rotor.vertex_count,0)
            self.assertGreater(len({round(y,5) for y in rotor.vertices[1::6]}),3)
            self.assertFalse(scene.metadata['detail']['gpu']['fan_blade_count_still_unverified'])
        self.assertFalse(profile_for(self.specs['gigabyte-fx5200-n52128d']['gpu']['appearance'])['render_ready'])

    def test_exact_fx_capacitor_line_sides_are_view_gated_real_edges_not_floating_rings(self):
        from assembly_geometry import build_scene
        from liquid_silhouette046 import clip_edge
        scene=build_scene(self.specs[MANUAL_ID])
        bodies=[m for m in scene.meshes if m.name.startswith('detail-gpu-fx5200-observed-capacitor-body-')]
        self.assertEqual(len(bodies),6)
        for body in bodies:
            arrays=body.vertices
            lines=edge_batches((body,),'notebook_line')[0][1];self.assertLessEqual(len(lines)//12,512)
            actual=set()
            key=lambda p:tuple(round(x,7) for x in p)
            for n in range(0,len(arrays),18):
                points=[key(arrays[n+j:n+j+3]) for j in (0,6,12)]
                actual.update(tuple(sorted((points[a],points[b]))) for a,b in ((0,1),(1,2),(2,0)))
            side=[]
            for n in range(0,len(lines),12):
                a,b,tag=lines[n:n+3],lines[n+6:n+9],lines[n+3:n+6]
                if tag[2]==-2.:
                    def on_edge(p,edge):
                        u,v=edge;delta=tuple(v[k]-u[k] for k in range(3));length2=dot(delta,delta)
                        t=dot(tuple(p[k]-u[k] for k in range(3)),delta)/length2 if length2 else -1
                        return -1e-7<=t<=1+1e-7 and math.dist(p,tuple(u[k]+t*delta[k] for k in range(3)))<1e-6
                    # Notebook's retained collinear midpoint may split one
                    # genuine long edge. Both ends must lie on that same edge.
                    self.assertTrue(any(on_edge(a,e) and on_edge(b,e) for e in actual),'ink segment left actual triangle edge')
                    if abs(a[1]-b[1])>1:side.append((a,b,tag))
            self.assertGreaterEqual(len(side),12)
            for direction in ((.3,-.8,.5),(1.,-.4,.1),(-.5,-.3,1.)):
                self.assertGreaterEqual(sum(bool(clip_edge(a,b,tag,direction=direction)) for a,b,tag in side),2)
            unrelated=edge_batches((replace(body,name='old-unrelated-cylinder'),),'notebook_line')[0][1]
            self.assertFalse(any(unrelated[n+5]==-2. for n in range(0,len(unrelated),12)))
            self.assertIs(body.vertices,arrays)

    def test_actual_native_all_six_styles_retain_eight_packages_and_six_caps(self):
        from PySide6.QtQml import QQmlExpression,qmlContext
        appearance=self.specs[MANUAL_ID]['gpu']['appearance']
        for style in SIX:
            expression=QQmlExpression(qmlContext(self.source_object),self.source_object,
                'art('+json.dumps(appearance)+','+json.dumps(style)+')')
            source=expression.evaluate()
            if isinstance(source,tuple):source=source[0]
            self.assertFalse(expression.hasError());svg=unquote(source.split(',',1)[1]);root=ET.fromstring(svg)
            for tag,count in (('hardware-fx052-memory',8),('hardware-fx052-capacitor',6)):
                self.assertEqual(sum(tag in row.get('class','').split() for row in root.iter()),count,(style,tag))
            contacts=[row for row in root.iter() if 'hardware-fx052-agp-segment' in row.get('class','').split()]
            self.assertEqual(len(contacts),3,style)
            self.assertEqual([(float(row.get('data-u0')),float(row.get('data-u1')))for row in contacts],
                             [(.385,.525),(.535,.647),(.658,.800)],style)


if __name__=='__main__':unittest.main()
