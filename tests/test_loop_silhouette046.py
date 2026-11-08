"""Actual retained smooth silhouettes, shared camera rule and legacy VBO bytes."""
import ast
import hashlib
import math
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,box,color,ring
from assembly_style import apply_model_styles,crease_edges,edge_batches
from liquid_silhouette046 import (CREASE_TAG,clip_edge,decode_normals,
                                  encode_normals,silhouette_edges)
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]
dot=lambda a,b:sum(x*y for x,y in zip(a,b))
key=lambda a,b:tuple(sorted(tuple(round(v,7) for v in p) for p in (a,b)))


def moved(vertices,angle=.61):
    c,s=math.cos(angle),math.sin(angle)
    rotate=lambda p:(c*p[0]+s*p[2],p[1],-s*p[0]+c*p[2])
    return tuple(v for at in range(0,len(vertices),6) for p in
                 (rotate(vertices[at:at+3]),rotate(vertices[at+3:at+6])) for v in p)


def batch_rows(data):
    return tuple((data[n:n+3],data[n+6:n+9],data[n+3:n+6]) for n in range(0,len(data),12))


class LoopSilhouette046Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(name,side_effect=AssertionError('Static local ink only')))

    def test_two_normals_pack_exact_float32_and_decode_finite_with_small_error(self):
        maximum=0.
        normals=[(1.,0.,0.),(-1.,0.,0.),(0.,0.,1.),(0.,0.,-1.),(0.,1.,0.)]
        for n in range(1000):
            z=1.-2.*(n+.5)/1000.;a=n*2.399963229728653
            normals.append((math.sqrt(1-z*z)*math.cos(a),math.sqrt(1-z*z)*math.sin(a),z))
        for n in normals:
            tag=encode_normals(n,tuple(-v for v in n))
            self.assertEqual(struct.unpack('<3f',struct.pack('<3f',*tag)),tag)
            for source,decoded in zip((n,tuple(-v for v in n)),decode_normals(tag)):
                self.assertAlmostEqual(dot(decoded,decoded),1.,places=12)
                maximum=max(maximum,math.degrees(math.acos(max(-1.,min(1.,dot(source,decoded))))))
        self.assertLess(maximum,.065)
        self.assertIsNone(decode_normals(CREASE_TAG))
        self.assertIsNone(decode_normals((float('nan'),0.,-2.)))
        self.assertIsNone(decode_normals((16777216.,0.,-2.)))

    def test_all24_and32_face_cylinder_yaws_and_slanted_axis_keep_complete_contours(self):
        for count in (24,32):
            for angle in (0.,.61):
                vertices=moved(ring(10.,6.,30.,count),angle)
                edges,tags,groups=silhouette_edges(vertices,crease_edges(vertices,repair_under_cap=True))
                candidates=[(a,b,tag) for (a,b),tag in zip(edges,tags) if decode_normals(tag)]
                self.assertEqual(len(candidates),count*2)
                self.assertEqual(sorted(len(group) for group,_ in groups),[count,count])
                for yaw in range(360):
                    a=math.radians(yaw+.37)
                    for pitch in (0.,.31,.95):
                        view=(math.cos(a)*math.cos(pitch),math.sin(a)*math.cos(pitch),math.sin(pitch))
                        c,s=math.cos(angle),math.sin(angle)
                        direction=(c*view[0]+s*view[2],view[1],-s*view[0]+c*view[2])
                        visible=[edge for edge in candidates if clip_edge(*edge,direction=direction)]
                        self.assertEqual(len(visible),4,(count,angle,yaw,pitch))

    def test_tagged_candidates_are_exact_real_triangle_edges_not_proxy_meridians(self):
        vertices=moved(ring(10.,6.,30.,32))
        real=set()
        for at in range(0,len(vertices),18):
            p=[vertices[at+n:at+n+3] for n in (0,6,12)]
            real.update(key(a,b) for a,b in zip(p,p[1:]+p[:1]))
        edges,tags,_=silhouette_edges(vertices,crease_edges(vertices,repair_under_cap=True))
        self.assertTrue(all(key(*edge) in real for edge,tag in zip(edges,tags) if decode_normals(tag)))
        self.assertTrue(any(decode_normals(tag) for tag in tags))
        self.assertEqual(silhouette_edges(box(12.,15.,20.),crease_edges(box(12.,15.,20.)))[1],
                         (CREASE_TAG,)*12)

    def test_perspective_clip_uses_exact_roots_and_matches_fragment_signs(self):
        tag=encode_normals((1.,0.,0.),(.8,.6,0.));a=(-2.,0.,0.);b=(2.,0.,0.);eye=(0.,1.,5.)
        segments=clip_edge(a,b,tag,eye=eye)
        self.assertEqual(len(segments),1)
        self.assertGreater(segments[0][1][0]-segments[0][0][0],.70)
        self.assertLess(segments[0][1][0]-segments[0][0][0],.80)
        normals=decode_normals(tag)
        for n in range(1001):
            t=(n+.23)/1001.;p=tuple(a[k]+(b[k]-a[k])*t for k in range(3))
            signs=[dot(normal,tuple(eye[k]-p[k] for k in range(3))) for normal in normals]
            expected=min(signs)<=0.<=max(signs)
            actual=any(low[0]-1e-10<=p[0]<=high[0]+1e-10 for low,high in segments)
            self.assertEqual(actual,expected)
        self.assertEqual(clip_edge(a,b,CREASE_TAG),((a,b),))
        self.assertEqual(clip_edge(a,b,tag,direction=(1.,1.,1.)),())
        with self.assertRaises(ValueError):clip_edge(a,b,tag)

    def test_groups_are_whole_and_main_cylinder_kept_under_mesh512(self):
        major=ring(20.,12.,100.,32);vertices=list(major)
        for n in range(12):
            small=ring(2.,1.,3.,24)
            for at in range(0,len(small),6):vertices.extend((small[at]+100+n*8.,*small[at+1:at+6]))
        vertices=tuple(vertices);old=crease_edges(vertices,repair_under_cap=True)
        edges,tags,groups=silhouette_edges(vertices,old,split_long=True)
        self.assertLessEqual(sum(1+int(math.dist(*edge)>12.) for edge in edges),512)
        major_candidates=[edge for edge,tag in zip(edges,tags) if decode_normals(tag) and abs(edge[0][0])<=20.0001]
        self.assertEqual(len(major_candidates),64)
        self.assertTrue(all(len(group) in (24,32) for group,_ in groups))
        self.assertEqual(silhouette_edges(vertices,old,0),((),(),()))

    def test_actual_batches_share_tags_and_obey_mesh_and_scene_caps_atomically(self):
        vertices=ring(20.,12.,100.,32)
        meshes=tuple(Mesh('loop-tank-'+str(n),vertices,color('#768e99'),position=(n*50.,0.,0.),component='cooler') for n in range(48))
        batches=edge_batches(meshes,'notebook_line')
        self.assertLessEqual(sum(len(data)//12 for _,data in batches),8192)
        self.assertTrue(batches)
        for mesh,data in batches:
            self.assertLessEqual(len(data)//12,512)
            candidates=[]
            for at in range(0,len(data),12):
                self.assertEqual(data[at+3:at+6],data[at+9:at+12])
                if decode_normals(data[at+3:at+6]):candidates.append(data[at:at+12])
            # Each ring has two smooth surfaces, each with32 long edges; hand
            # subdivision duplicates each complete group to64 segments.
            self.assertIn(len(candidates),(0,64,128))
            for yaw in (13.37,71.37,145.37,243.37):
                v=(math.cos(math.radians(yaw)),math.sin(math.radians(yaw)),.25)
                count=sum(bool(clip_edge(a,b,tag,direction=v)) for a,b,tag in batch_rows(data) if decode_normals(tag))
                self.assertIn(count,(0,4,8))

    def test_all13_styles_keep_physical_arrays_and_only_loop_line_styles_tagged(self):
        source=Mesh('loop-test-cylinder',ring(10.,6.,30.,24),color('#667f88'),component='cooler')
        for style in HARDWARE_ICON_STYLES:
            meshes,metadata=apply_model_styles((source,),style,{},(40.,40.,40.),{'front':'open'})
            self.assertIs(meshes[0].vertices,source.vertices)
            batches=edge_batches(meshes,style,metadata['mesh_style_ids'])
            has_tag=any(decode_normals(data[n+3:n+6]) for _,data in batches for n in range(0,len(data),12))
            self.assertEqual(has_tag,style in ('outline','notebook_line','sketch'))

    def test_all_legacy_nonloop_vbo_bytes_equal_frozen_fixture(self):
        meshes=(Mesh('legacy-cylinder',ring(10.,6.,30.,24),color('#677f8a'),component='cooler',part_id='cooler:legacy'),
                Mesh('legacy-box',box(24.,18.,12.),color('#81949d'),component='case',part_id='case'))
        plain='4c3325aaf55e785e72a0dc5462fcad62c07325a64b30b48f6b2b9247a3e6fb0a'
        hand='2183a7caba4e45f75f3c251bde18022e6db3d59a36d7c35d2c1e69c10746dcef'
        ink='c359e952397e0d5f93b0f1b8f455855f91f8a11f63573458f8112c0188cbaa1c'
        expected={style:plain for style in HARDWARE_ICON_STYLES}
        expected.update(miniature=hashlib.sha256(b'').hexdigest(),notebook_color=hand,notebook_line=hand,
                        sketch=hand,notebook_smile=hand,solid=ink,papercut=ink)
        for style in HARDWARE_ICON_STYLES:
            digest=hashlib.sha256()
            with patch('liquid_silhouette046.silhouette_edges',side_effect=AssertionError('Legacy bypass')):
                for mesh,data in edge_batches(meshes,style):
                    digest.update(mesh.name.encode());digest.update(struct.pack('<I',len(data)))
                    digest.update(struct.pack('<'+str(len(data))+'f',*data))
            self.assertEqual(digest.hexdigest(),expected[style],style)

    def test_glsl_retains_stride_and_uses_existing_view_with_no_cpu_frame_rebuild(self):
        module=ast.parse((ROOT/'assembly_viewer.py').read_text('utf8'))
        values={n.targets[0].id:ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign)
                and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('VERTEX_SHADER','FRAGMENT_SHADER')}
        vertex=values['VERTEX_SHADER'];fragment=values['FRAGMENT_SHADER']
        self.assertIn('oct12Normal(normal.x)',vertex);self.assertIn('oct12Normal(normal.y)',vertex)
        self.assertIn('normal.z < -1.5',vertex);self.assertIn('flat out float silhouetteEdge',vertex)
        self.assertIn('dot(adjacentNormal,v)',fragment);self.assertIn('min(a,b)>0.0||max(a,b)<0.0',fragment)
        source=(ROOT/'assembly_viewer.py').read_text('utf8')
        self.assertEqual(source.count('for mesh,vertices in edge_batches('),1)
        self.assertIn('setAttributeBuffer(1,GL_FLOAT,12,3,24)',source)


if __name__=='__main__':unittest.main()
