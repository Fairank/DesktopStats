"""Crowded whole-PC ink keeps complete structure before sampled detail."""
import copy
import math
import unittest

from assembly_geometry import Mesh,box,ring,build_scene
from assembly_style import crease_edges,edge_batches,_edge_groups,MAX_STYLE_EDGES
from liquid_silhouette046 import decode_normals
from tests import test_loop_assembly046 as fixtures


def retained(edge,data):
    a,b=edge;delta=tuple(b[k]-a[k] for k in range(3));den=sum(v*v for v in delta)
    def projected(p):
        t=sum((p[k]-a[k])*delta[k] for k in range(3))/den if den else 0.
        return t if math.dist(p,tuple(a[k]+delta[k]*t for k in range(3)))<.002 else None
    intervals=[]
    for n in range(0,len(data),12):
        p,q=projected(data[n:n+3]),projected(data[n+6:n+9])
        if p is not None and q is not None:
            low,high=max(0.,min(p,q)),min(1.,max(p,q))
            if high>=low:intervals.append((low,high))
    end=0.
    for low,high in sorted(intervals):
        if low>end+.0001:return False
        end=max(end,high)
    return end>=.9999


def same_path(a,b):
    return (all(retained((a[n:n+3],a[n+6:n+9]),b) for n in range(0,len(a),12)) and
            all(retained((b[n:n+3],b[n+6:n+9]),a) for n in range(0,len(b),12)))


class AssemblyInkPriority046Tests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LoopAssembly046Tests.setUpClass.__func__)
    setUp=fixtures.LoopAssembly046Tests.setUp
    tearDown=fixtures.LoopAssembly046Tests.tearDown

    def reference_scene(self):
        from stats_config import DEFAULT
        from assembly_spec import build_spec
        config=copy.deepcopy(DEFAULT)
        config['assembly'].update(case_model='cooler-master-haf-700-evo',cpu_model='intel-13700kf',
            gpu_model='asus-astral-5090',board_model='asus-rog-strix-z790-a-wifi-d4',
            memory_models=['gskill-f4-3200c16d-16gtzr']*2,psu_model='corsair-rm1000x-2024',
            storage=[dict(model_id='samsung-990-pro-2tb',count=1)],
            cooler_model='custom-loop-360-reference',cooler_mount='top',detail_level='eco',
            gpu_waterblock=False,loop_components_mode='selected',cpu_block_model=fixtures.BLOCK,
            pump_reservoir_model=fixtures.COMBO,fitting_model=fixtures.FITTING,tubing_model=fixtures.TUBING,
            radiator_model='corsair-xr5-360',radiator_fan_layout='single',radiator_fan_model='arctic-p12-pwm',
            case_fans=[dict(model='arctic-p12-pwm',mount='front',count=3,direction='intake'),
                       dict(model='arctic-p12-pwm',mount='rear',count=1,direction='exhaust')],
            cables_enabled=True,fan_motion='demo',fan_animation=True)
        return build_scene(build_spec({},config,{},[]))

    def test_actual_haf_selected_full_reference_keeps_all12_beams_complete(self):
        scene=self.reference_scene()
        beams=[m for m in scene.meshes if m.name in ('case-upright','case-width-rail','case-depth-rail')]
        self.assertEqual(len(beams),12)
        # HAF's PSU belongs behind the motherboard. Its source-observed
        # lower cooling bracket and motherboard tray replace the old filled
        # main-chamber PSU cover; retain their complete primary outer rims.
        shroud=scene.metadata['case_shroud']
        self.assertEqual(shroud['case_id'],'cooler-master-haf-700-evo')
        self.assertFalse(shroud['horizontal_psu_cover_present'])
        self.assertEqual(shroud['psu_chamber'],'behind_motherboard_lower_rear')
        self.assertTrue(shroud['layout_reference']['main_chamber_is_not_a_psu_bay'])
        self.assertFalse(any(m.component=='case' and m.name=='psu-shroud' for m in scene.meshes))
        source_names={'case:bottom-cooling-support':'case-bottom-cooling-support',
                      'case:motherboard-tray':'case-haf-motherboard-tray'}
        source_structures=[]
        for identity,name in source_names.items():
            rows=[m for m in scene.meshes if m.component=='case' and m.part_id==identity]
            self.assertEqual(len(rows),1,identity)
            self.assertEqual(rows[0].name,name)
            declared=[r for r in shroud['parts'] if r['id']==identity]
            self.assertEqual(len(declared),1,identity)
            self.assertEqual((declared[0]['kind'],declared[0]['component'],declared[0]['model_id']),
                             ('case_structure','case','cooler-master-haf-700-evo'))
            self.assertFalse(declared[0]['dimensions_verified'])
            self.assertTrue(declared[0]['source_urls'])
            self.assertTrue(any(r['id']==identity for r in scene.metadata['hardware']['parts']))
            source_structures.append(rows[0])
        for style in ('outline','notebook_line','sketch'):
            batches=edge_batches(scene.meshes,style);lookup={id(m):data for m,data in batches}
            self.assertLessEqual(sum(len(data)//12 for _,data in batches),MAX_STYLE_EDGES)
            self.assertLessEqual(max(len(data)//12 for _,data in batches),512)
            for mesh in beams:
                edges=crease_edges(mesh.vertices);self.assertEqual(len(edges),12)
                self.assertTrue(all(retained(edge,lookup[id(mesh)]) for edge in edges),(style,mesh.name))
            for mesh in source_structures:
                edges=crease_edges(mesh.vertices);groups=_edge_groups(edges)
                self.assertTrue(groups,(style,mesh.part_id))
                maximum=max(span for _,span in groups)
                physical_span=max(max(mesh.vertices[k::6])-min(mesh.vertices[k::6]) for k in range(3))
                self.assertAlmostEqual(maximum,physical_span,places=3)
                # Both faces of each primary perimeter must remain closed.
                # Internal sampled vent/hole groups need not all consume the
                #512-mesh/global8192 budget in this crowded complete host.
                primary=[group for group,span in groups if span>=maximum*.9]
                self.assertGreaterEqual(sum(map(len,primary)),8,(style,mesh.part_id))
                for group in primary:
                    degree={}
                    for index in group:
                        for point in edges[index]:degree[point]=degree.get(point,0)+1
                    self.assertTrue(degree and all(value>=2 for value in degree.values()),
                                    (style,mesh.part_id,'closed physical main perimeter'))
                    self.assertTrue(all(retained(edges[index],lookup.get(id(mesh),())) for index in group),
                                    (style,mesh.part_id,'complete source main perimeter'))
            tubes=[m for m in scene.meshes if m.name=='loop-reference-routed-tube']
            self.assertEqual(len(tubes),3)
            for mesh in tubes:
                isolated=next(data for m,data in edge_batches((mesh,),style) if m is mesh)
                self.assertTrue(same_path(lookup.get(id(mesh),()),isolated),(style,mesh.part_id,'mouth and complete long-side groups'))
            tank_parts=[m for m in scene.meshes if m.name.startswith(('loop-xd5-rounded-rectangular-clear-tank',
                        'loop-source-hydraulic-reservoir-base','loop-square-source-reservoir-lid')) or
                        m.name=='loop-sold-included-pump-motor']
            self.assertEqual(len(tank_parts),10)
            for tank in tank_parts:
                single=next(data for m,data in edge_batches((tank,),style) if m is tank)
                self.assertTrue(same_path(lookup.get(id(tank),()),single),(style,tank.name,'tank long walls and cap rings'))
            block_parts=[m for m in scene.meshes if m.name.startswith('loop-cpu-source-shell')]
            self.assertEqual(len(block_parts),3)
            for block in block_parts:
                single=next(data for m,data in edge_batches((block,),style) if m is block)
                self.assertTrue(same_path(lookup.get(id(block),()),single),(style,block.name,'block shell and true port openings'))
            board=next(m for m in scene.meshes if m.name=='motherboard-reference')
            edges=crease_edges(board.vertices);groups=_edge_groups(edges);maximum=max(span for _,span in groups)
            self.assertTrue(all(retained(edges[n],lookup[id(board)]) for group,span in groups if span>=maximum*.9 for n in group))
            for mesh in (m for m in scene.meshes if m.rotor):
                edges=crease_edges(mesh.vertices);groups=_edge_groups(edges);maximum=max(span for _,span in groups)
                threshold=max(maximum*.14,min(12.,maximum*.30))
                main={n for group,span in groups if span>=threshold for n in group}
                data=lookup.get(id(mesh),())
                self.assertTrue(all(retained(edges[n],data) for n in main),(style,mesh.name,mesh.part_id))
            fixed=[m for m in scene.meshes if m.name in ('gpu-fan-opening','gpu-fan-hub','gpu-shroud','gpu-backplate','gpu-pcb')
                   or m.name.endswith('-fan-frame')]
            self.assertEqual(sum(m.name.endswith('-fan-frame') for m in fixed),7)
            for mesh in fixed:
                edges=crease_edges(mesh.vertices);groups=_edge_groups(edges);maximum=max(span for _,span in groups)
                self.assertTrue(all(retained(edges[n],lookup.get(id(mesh),())) for group,span in groups
                                    if span>=maximum*.45 for n in group),(style,mesh.name,mesh.part_id,'paired fixed outline'))
            for mesh in (m for m in scene.meshes if m.name.startswith('front-display')):
                data=lookup.get(id(mesh),());edges=crease_edges(mesh.vertices)
                for group,_ in _edge_groups(edges):
                    kept=[retained(edges[n],data) for n in group]
                    self.assertIn(sum(kept),(0,len(kept)))

    def test_dense_grilles_cannot_starve_frame_fan_leaves_or_split_smooth_groups(self):
        from assembly_cooling import add_cooling
        fans,_=add_cooling((),{'cooling':{'case_fans':[dict(model='noctua-nf-a12x25-pwm',mount='front',count=1)]}},
                          anchors={'case_dimensions':(600.,800.,800.)})
        rotor=next(mesh for mesh in fans if mesh.rotor)
        frame=Mesh('case-main-frame',box(5.,450.,5.),(.4,.5,.6,1.),component='case')
        cylinder=Mesh('loop-main-tank-housing',ring(20.,12.,100.,32),(.4,.5,.6,1.),component='cooler')
        grille=box(200.,200.,1.)
        fillers=tuple(Mesh('case-perforated-grille-reference',grille,(.4,.5,.6,1.),component='case',position=(n,0.,0.)) for n in range(400))
        meshes=(*fillers,*fans,cylinder,frame)
        batches=edge_batches(meshes,'notebook_line');lookup={id(mesh):data for mesh,data in batches}
        self.assertLessEqual(sum(len(data)//12 for _,data in batches),MAX_STYLE_EDGES)
        self.assertLessEqual(max(len(data)//12 for _,data in batches),512)
        self.assertTrue(all(retained(edge,lookup[id(frame)]) for edge in crease_edges(frame.vertices)))
        edges=crease_edges(rotor.vertices);groups=_edge_groups(edges);maximum=max(span for _,span in groups)
        threshold=max(maximum*.14,min(12.,maximum*.30))
        main={n for group,span in groups if span>=threshold for n in group}
        self.assertTrue(main)
        self.assertTrue(all(retained(edges[n],lookup[id(rotor)]) for n in main))
        data=lookup[id(cylinder)];count=sum(decode_normals(data[n+3:n+6]) is not None for n in range(0,len(data),12))
        self.assertEqual(count,64)  # Same64 real edges, no collinear decorative midpoints.
        self.assertLessEqual(len(data)//12,512)

    def test_existing_single_frame_plus700_contacts_remains_closed(self):
        frame=Mesh('case-side-mount-frame',box(5.,450.,5.),(.4,.5,.6,1.))
        pins=tuple(Mesh('board-socket-spring-heads',box(2.,2.,1.),(.4,.5,.6,1.),
                        position=(n,0.,0.),component='board') for n in range(700))
        for style,expected in (('outline',12),('notebook_line',16)):
            batches=edge_batches((*pins,frame),style)
            data=next(v for m,v in batches if m is frame)
            self.assertEqual(len(data)//12,expected)
            self.assertTrue(all(retained(edge,data) for edge in crease_edges(frame.vertices)))
            self.assertLessEqual(sum(len(v)//12 for _,v in batches),MAX_STYLE_EDGES)


if __name__=='__main__':unittest.main()
