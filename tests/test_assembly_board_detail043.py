"""Real connector openings/contact isolation, all reviewed board poses, no I/O."""
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,box,build_scene
from assembly_motherboard import enrich_motherboard,layout_anchors
from assembly_scene_cache import SceneCache
from hardware_appearance import appearance_for
from motherboard_catalog import MODELS
from top_bar_config import HARDWARE_ICON_STYLES


def spec(identity='asus-rog-strix-z790-a-wifi-d4'):
    return dict(case=dict(layout='tower',dimensions_mm=dict(width=250,height=500,depth=500)),
        board=dict(model_id=identity),cpu=dict(style='lga_rect',appearance=appearance_for('cpu','Intel Core i7-13700KF')),
        memory=dict(count=0,modules=[]),detail_level='balanced')


def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def add(a,b):return tuple(x+y for x,y in zip(a,b))
def mul(a,t):return tuple(x*t for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def segment_hit(mesh,start,end):
    """Independent finite Moller-Trumbore query, including real open cavities."""
    direction=sub(end,start)
    for offset in range(0,len(mesh.vertices),18):
        a,b,c=(add(mesh.vertices[offset+k:offset+k+3],mesh.position) for k in (0,6,12))
        e,f=sub(b,a),sub(c,a);p=cross(direction,f);det=dot(e,p)
        if abs(det)<1e-10:continue
        t=sub(start,a);u=dot(t,p)/det
        if u<0 or u>1:continue
        q=cross(t,e);v=dot(direction,q)/det
        if v<0 or u+v>1:continue
        distance=dot(f,q)/det
        if 0<=distance<=1:return True
    return False


class AssemblyBoardDetail043Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('Board detail construction is pure geometry')))

    @staticmethod
    def board(identity='asus-rog-strix-z790-a-wifi-d4',level='balanced'):
        value=spec(identity);value['detail_level']=level
        anchors=layout_anchors(value,250,500,500,90,10,-236)
        meshes,metadata=enrich_motherboard((),value,anchors,level)
        return meshes,metadata,anchors

    def test_all_sixteen_boards_three_lods_keep_counts_open_socket_envelopes_and_finite_normals(self):
        self.assertEqual(len(MODELS),16)
        for model in MODELS:
            for level in ('eco','balanced','close'):
                with self.subTest(board=model['id'],level=level):
                    meshes,meta,a=self.board(model['id'],level)
                    count=sum(len(a['connectors'].get(kind,()))*pins for kind,pins in (('atx24',24),('eps8',8),('eps4',4),('aux6',6)))
                    contacts=[m for m in meshes if m.name=='board-power-independent-contacts']
                    self.assertEqual(len(contacts),1);self.assertEqual(contacts[0].vertex_count,count*36)
                    self.assertEqual(meta['power_contact_count'],count)
                    self.assertTrue(meta['power_contacts_independent']);self.assertTrue(meta['connector_contact_shape_reference'])
                    self.assertFalse(meta['connector_oem_identified']);self.assertFalse(meta['m2_contact_map_drawn'])
                    sockets=[m for m in meshes if m.name=='detail-board-m2-socket']
                    self.assertEqual(len(sockets),len(model['m2']))
                    self.assertEqual(meta['m2_receiving_channel_count'],len(sockets))
                    self.assertTrue(all(m.vertex_count==4*36 for m in sockets))
                    for mesh in (*contacts,*sockets):
                        self.assertTrue(all(math.isfinite(v) for v in mesh.vertices))
                        for i in range(0,len(mesh.vertices),6):
                            self.assertAlmostEqual(sum(v*v for v in mesh.vertices[i+3:i+6]),1.,places=7)
                    # Delta over the original one-box M.2 socket and no posts.
                    # The footprint changes neither LOD nor the product count.
                    extra_triangles=count*12+len(sockets)*36
                    self.assertLessEqual(extra_triangles,1200)

    def test_individual_power_posts_match_every_cavity_grid_without_a_conductive_bridge(self):
        meshes,meta,a=self.board();contacts=next(m for m in meshes if m.name=='board-power-independent-contacts')
        expected=[]
        for key,cols in (('atx24',12),('eps8',4),('eps4',2),('aux6',3)):
            for anchor in a['connectors'].get(key,()):
                n,along=anchor['normal'],anchor['along'];across=cross(n,along)
                for col in range(cols):
                    for row in range(2):
                        expected.append(add(add(anchor['position'],mul(n,-4.2)),add(mul(along,(col-(cols-1)/2)*4.2),mul(across,(row-.5)*4.2))))
        actual=[]
        for offset in range(0,len(contacts.vertices),216):
            values=contacts.vertices[offset:offset+216]
            actual.append(tuple((min(values[k::6])+max(values[k::6]))/2 for k in range(3)))
        quant=lambda p:tuple(round(v,6) for v in p)
        self.assertEqual(sorted(map(quant,actual)),sorted(map(quant,expected)))
        anchor=a['connectors']['atx24'][0];n=anchor['normal'];along=anchor['along'];across=cross(n,along)
        # A ray reaches each post through its existing well. The midpoint
        # between adjacent wells never hits a hidden continuous copper slab.
        for col in range(12):
            p=add(anchor['position'],add(mul(along,(col-5.5)*4.2),mul(across,-2.1)))
            self.assertTrue(segment_hit(contacts,add(p,mul(n,20)),add(p,mul(n,-10))))
        gap=add(anchor['position'],add(mul(along,-5*4.2),mul(across,-2.1)))
        self.assertFalse(segment_hit(contacts,add(gap,mul(n,20)),add(gap,mul(n,-10))))
        for floor in (m for m in meshes if m.name.endswith('-contact-floor') and any(key in m.name for key in ('atx24','eps8','eps4','aux6'))):
            self.assertEqual(floor.color,tuple(int('#171c22'[i:i+2],16)/255 for i in (1,3,5))+(1.,))

    def test_m2_mouth_is_open_along_each_real_front_or_rear_card_axis(self):
        sides=set();axes=set()
        for model in MODELS:
            meshes,meta,a=self.board(model['id'])
            sockets=[m for m in meshes if m.name=='detail-board-m2-socket']
            for mesh,anchor in zip(sockets,a['connectors']['m2']):
                with self.subTest(board=model['id'],side=anchor['side'],along=anchor['along']):
                    sides.add(anchor['side']);axes.add(anchor['along'])
                    p=anchor['position'];along=anchor['along'];n=(1.,0.,0.) if anchor['side']=='rear' else (-1.,0.,0.)
                    across=cross(n,along)
                    start=add(p,mul(along,8));inside=add(p,mul(along,.1))
                    self.assertFalse(segment_hit(mesh,start,inside),'The card mouth was filled or faced the wrong axis')
                    self.assertTrue(segment_hit(mesh,start,add(p,mul(along,-3))),'The rear wall must remain')
                    side=add(p,mul(across,10.5))
                    self.assertTrue(segment_hit(mesh,add(side,mul(along,8)),add(side,mul(along,.1))))
                    floor=add(p,mul(along,.5))
                    self.assertTrue(segment_hit(mesh,add(floor,mul(n,5)),add(floor,mul(n,-2))))
                    # The same exact old reference envelope, with an empty
                    # receiving channel instead of another solid component.
                    sizes=sorted(max(mesh.vertices[k::6])-min(mesh.vertices[k::6]) for k in range(3))
                    for actual,expected in zip(sizes,(3.2,5.,22.)):self.assertAlmostEqual(actual,expected)
        self.assertEqual(sides,{'front','rear'});self.assertGreaterEqual(len(axes),3)

    def test_documented_m2_posts_keep_allowed_lengths_and_do_not_assume_installed_ssds(self):
        for model in MODELS:
            meshes,meta,a=self.board(model['id'])
            posts=[m for m in meshes if m.name=='detail-board-m2-mount-post']
            expected=[add(anchor['position'],mul(anchor['along'],distance)) for anchor in a['connectors']['m2'] for distance in anchor['allowed_lengths_mm']]
            self.assertEqual([m.position for m in posts],expected)
            self.assertFalse(meta['installed_ssd_count_inferred'])
            self.assertEqual(meta['layout_source'],model['manual'])
            self.assertTrue(all(source.startswith('https://') for source in meta['interface_detail_sources']))

    def test_all_thirteen_styles_share_the_same_physical_detail_arrays_and_anchors(self):
        value=spec();cache=SceneCache();base=cache.build(value)
        for style in HARDWARE_ICON_STYLES:
            with self.subTest(style=style):
                current=cache.build(dict(value,visual_style=style))
                self.assertEqual(current.metadata['attachment_anchors'],base.metadata['attachment_anchors'])
                self.assertEqual(current.metadata['motherboard']['power_contact_count'],40)
                for original,painted in zip(base.meshes,current.meshes):
                    self.assertIs(original.vertices,painted.vertices)
                    self.assertEqual(original.position,painted.position)
                    self.assertEqual(original.rotor,painted.rotor)

    def test_power_contact_batches_follow_final_board_rigid_poses_including_bench_translation(self):
        from chassis_catalog import get_case
        cases=[dict(layout=layout,dimensions_mm=dict(width=250,height=500,depth=500))
               for layout in ('tower','vertical','horizontal')]+[get_case('streacom-bc1-v2')]
        for case in cases:
            with self.subTest(case=case.get('id',case['layout'])):
                value=spec();value['case']=case;scene=build_scene(value)
                a=scene.metadata['attachment_anchors'];contacts=next(m for m in scene.meshes if m.name=='board-power-independent-contacts')
                expected=[]
                for key,columns in (('atx24',12),('eps8',4),('eps4',2),('aux6',3)):
                    for row in a['connectors'].get(key,()):
                        n,axis=row['normal'],row['along'];across=cross(n,axis)
                        for col in range(columns):
                            for side in (-.5,.5):
                                expected.append(add(add(row['position'],mul(n,-4.2)),add(mul(axis,(col-(columns-1)/2)*4.2),mul(across,side*4.2))))
                actual=[]
                for offset in range(0,len(contacts.vertices),216):
                    v=contacts.vertices[offset:offset+216]
                    actual.append(add(contacts.position,tuple((min(v[k::6])+max(v[k::6]))/2 for k in range(3))))
                rounded=lambda p:tuple(round(v,5) for v in p)
                self.assertEqual(sorted(map(rounded,actual)),sorted(map(rounded,expected)))

    def test_unmatched_board_does_not_acquire_contacts_or_a_reference_socket(self):
        original=(Mesh('unchanged',box(2,3,4),(1,1,1,1)),)
        result,meta=enrich_motherboard(original,{},None)
        self.assertIs(result,original);self.assertEqual(meta,{})


if __name__=='__main__':unittest.main()
