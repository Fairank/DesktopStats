"""Real optional loop-pack consumption and fail-closed static assembly fixtures.

Author catalogs prepare a data archive once. Runtime paths are guarded against
author imports, native APIs, devices, network, workers, Qt and visible windows.
"""
import builtins
import copy
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import hardware_packs as packs
from assembly_cooling import add_cooling
from assembly_geometry import build_scene
from assembly_style import apply_model_styles
from liquid_component_runtime046 import get_component
from liquid_pack_schema046 import validate_reference,validate_model,selector_for
from liquid_routes046 import route
from top_bar_config import HARDWARE_ICON_STYLES


ANCHORS={'cpu':{'position':(-35.,35.,10.),'normal':(-1.,0.,0.),'up':(0.,1.,0.)},
         'case_dimensions':(600.,800.,800.)}
BLOCK='alphacool-core1-black'
COMBO='corsair-xd5-rgb-gen2'
FITTING='alphacool-eiszapfen-soft-13-10'
TUBING='alphacool-alphatube-hf-13-10'
AUTHOR_MODULES=('liquid_block_pump_expansion046','liquid_fitting_tube_expansion046',
                'tools.export_loop_packs046')


def spec(**updates):
    selection=dict(cpu_cooler='custom-loop-360-reference',radiator_mount='top',
        radiator_model='corsair-xr5-360',radiator_fan_layout='none',
        loop_components_mode='selected',cpu_block_model=BLOCK,pump_reservoir_model=COMBO,
        fitting_model=FITTING,tubing_model=TUBING,loop_tubes_visible=True)
    selection.update(updates)
    return dict(cpu=dict(appearance=dict(cpu_package=dict(socket='LGA1700'))),cooling=selection)


def wrapper(row):
    return validate_model(dict(id=row['id'],label=row['label'],vendor=row['brand'],series=row['series'],
        aliases=[row['id']],sources=row['sources'],reference=row,selector=selector_for(row)))


def reasons(meta):
    return {r['reason'] for r in (*meta.get('loop_issues',()),*meta.get('rejected',()))}


def payload(meshes):
    return hashlib.sha256(repr([(m.name,m.vertices,m.position,m.color,m.component,m.rotor,m.direction,m.axis,m.part_id)
                                for m in meshes]).encode()).hexdigest()


class LoopAssembly046Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This is the authoring/export step, explicitly outside runtime guards.
        from tools.export_loop_packs046 import pack_models
        cls.library=pack_models()
        cls.references={r['id']:copy.deepcopy(r['reference']) for r in cls.library}
        cls.pack_bytes=packs.make_pack('test-loop046','Offline loop fixture',cls.library,kind='loop')
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No device, network, window or worker')))
        self.scratch=Path(self.enterContext(tempfile.TemporaryDirectory()))
        source=self.scratch/'source.dspack';source.write_bytes(self.pack_bytes)
        self.store=packs.PackStore(self.scratch/'installed');self.store.install(source)
        self.enterContext(patch.object(packs,'_store',self.store))
        original=builtins.__import__;self.author_imports=[]
        def guarded(name,*args,**kwargs):
            if name.startswith(AUTHOR_MODULES) or name.startswith(('PySide6','native_controller','process_snapshot')):
                self.author_imports.append(name)
                raise AssertionError('Runtime must not import author catalogs, Qt or collectors: '+name)
            return original(name,*args,**kwargs)
        self.enterContext(patch('builtins.__import__',new=guarded))
    def tearDown(self):
        self.assertEqual(self.author_imports,[])
    def build(self,value=None,meshes=(),anchors=None,level='eco'):
        return add_cooling(meshes,value or spec(),level,copy.deepcopy(anchors or ANCHORS))
    def assert_disconnected(self,meshes,meta,reason):
        self.assertIn(reason,reasons(meta))
        self.assertEqual(meta['selected_loop']['routes'],[])
        self.assertFalse(meta['selected_loop']['connected_reference_loop'])
        self.assertFalse(any(m.name=='loop-reference-routed-tube' for m in meshes))
        self.assertFalse(any(p['kind']=='tubing' for p in meta['parts']))
    @contextmanager
    def altered_reference(self,identity,**changes):
        row=copy.deepcopy(self.references[identity]);row.update(changes);validate_reference(row)
        real=get_component
        def getter(kind,key):
            if key==identity and kind==row['part_kind']:return copy.deepcopy(row)
            return real(kind,key)
        with patch('liquid_component_runtime046.get_component',side_effect=getter),\
             patch('assembly_loop046.get_component',side_effect=getter):yield row

    def test_default_reference_ignores_optional_component_fields_and_retains_legacy_payload(self):
        original=spec(loop_components_mode='reference')
        clean=copy.deepcopy(original)
        for key in ('loop_components_mode','cpu_block_model','pump_reservoir_model','fitting_model','tubing_model','loop_tubes_visible'):
            clean['cooling'].pop(key,None)
        with patch('assembly_loop046.get_component',side_effect=AssertionError('No selected-loop lookup')):
            plain,plain_meta=self.build(clean);retained,retained_meta=self.build(original)
        self.assertEqual(payload(plain),payload(retained))
        self.assertNotIn('selected_loop',plain_meta);self.assertNotIn('selected_loop',retained_meta)
        self.assertTrue(plain)
        empty,empty_meta=add_cooling((),{},anchors=ANCHORS)
        self.assertEqual(empty,());self.assertEqual(empty_meta['parts'],[])

    def test_real_archive_getter_producer_has_three_nodes_six_fittings_three_complete_routes(self):
        self.assertEqual(len(self.store.choices('loop')),len(self.library))
        self.assertEqual(get_component('cpu_block',BLOCK)['id'],BLOCK)
        self.assertEqual(get_component('pump',BLOCK),{})
        original=copy.deepcopy(spec());meshes,meta=self.build(original);loop=meta['selected_loop']
        self.assertEqual(set(loop['parts']),{'cpu_block_model','radiator_model','pump_reservoir_model'})
        fittings=[p for p in meta['parts'] if p['kind']=='fitting'];tubes=[p for p in meta['parts'] if p['kind']=='tubing']
        self.assertEqual(len(fittings),6);self.assertEqual(len(tubes),3);self.assertEqual(len(loop['routes']),3)
        self.assertTrue(loop['connected_reference_loop']);self.assertEqual(reasons(meta),set())
        keys={p['attached_port_key'] for p in fittings}
        self.assertEqual(keys,{'cpu_block_model:port1','cpu_block_model:port2',
            'radiator_model:connection-1','radiator_model:connection-2',
            'pump_reservoir_model:outlet','pump_reservoir_model:front-return'})
        # Extra return/fill openings are real nodes' ports, not extra default fittings.
        self.assertIn('top-fill',{p['id'] for p in loop['parts']['pump_reservoir_model']['ports']})
        self.assertFalse(any('top-fill' in key or 'rear-return' in key or 'top-return' in key for key in keys))
        fitted={p['attached_port_key']:p for p in fittings}
        from liquid_selection046 import fitting_ends
        a,b=fitting_ends(get_component('fitting',FITTING))
        for key,item in fitted.items():
            field,port_id=key.split(':');target=next(p for p in loop['parts'][field]['ports'] if p['id']==port_id)
            male=next(p for p in item['ports'] if p['id']==a['id'])
            self.assertLess(math.dist(target['position'],male['position']),1e-7)
            self.assertAlmostEqual(sum(x*y for x,y in zip(target['normal'],male['normal'])),-1.,places=6)
        for line in loop['routes']:
            for key,point in ((line['from_port'],line['points'][0]),(line['to_port'],line['points'][-1])):
                end=next(p for p in fitted[key]['ports'] if p['id']==b['id'])
                self.assertLess(math.dist(point,end['position']),1e-7)
            self.assertGreater(line['length_mm'],0.)
        self.assertFalse(meta['cpu_fan_tach_usable']);self.assertEqual(meta['real_cpu_rotor_parts'],[])
        self.assertFalse(any(m.rotor for m in meshes));self.assertFalse(loop['complete_installation_verified'])
        self.assertEqual(loop['new_pollers'],0);self.assertFalse(loop['flow_direction_verified'])
        self.assertEqual(original,spec());json.dumps(loop,allow_nan=False)

    def test_socket_mismatch_duplicate_combo_motor_and_bare_motor_without_top_remain_disconnected(self):
        wrong=spec();wrong['cpu']['appearance']['cpu_package']['socket']='LGA1151'
        for value,reason in ((wrong,'cpu_block_socket_unsupported'),
            (spec(pump_model='alphacool-vpp655-pwm'),'duplicate_loop_motor'),
            (spec(pump_reservoir_model='',pump_model='alphacool-vpp655-pwm',reservoir_model='watercool-heatkiller-tube100'),'missing_loop_pump_top')):
            with self.subTest(reason=reason):
                meshes,meta=self.build(value);self.assert_disconnected(meshes,meta,reason)

    def test_unverified_thread_and_gender_are_unknown_instead_of_claimed_compatible(self):
        for key,value in (('thread',None),('thread_gender','unknown')):
            ports=copy.deepcopy(self.references[BLOCK]['ports']);ports[0][key]=value
            with self.subTest(field=key),self.altered_reference(BLOCK,ports=ports):
                meshes,meta=self.build();self.assert_disconnected(meshes,meta,'port_thread_or_gender_unknown')

    def test_known_wrong_gender_and_both_tube_diameters_block_connections(self):
        for key,value in (('thread_gender','male'),('thread','G3/8')):
            ports=copy.deepcopy(self.references[BLOCK]['ports']);ports[0][key]=value
            with self.subTest(port_conflict=key),self.altered_reference(BLOCK,ports=ports):
                meshes,meta=self.build();self.assert_disconnected(meshes,meta,'port_thread_or_gender_mismatch')
        for key,value in (('tube_inner_mm',8.),('tube_outer_mm',16.)):
            row=copy.deepcopy(self.references[TUBING]);row[key]=value
            with self.subTest(dimension=key),self.altered_reference(TUBING,**{key:value}):
                meshes,meta=self.build();self.assert_disconnected(meshes,meta,'tube_diameter_mismatch')

    def test_insufficient_stock_or_bend_radius_discards_all_routes_and_tube_meshes(self):
        for changes,reason in (({'length_mm':20.},'tube_stock_length_exceeded'),
                               ({'min_bend_radius_mm':1000.},'tube_bend_radius_exceeded')):
            with self.subTest(reason=reason),self.altered_reference(TUBING,**changes):
                meshes,meta=self.build();self.assert_disconnected(meshes,meta,reason)

    def test_route_checks_whole_segments_case_wall_tube_radius_and_rigid_material(self):
        tube=copy.deepcopy(self.references[TUBING]);start=dict(position=(-40.,0.,0.),normal=(1.,0.,0.));end=dict(position=(40.,0.,0.),normal=(-1.,0.,0.))
        line,reason=route(start,end,tube,case_bounds=((-50.,-50.,-50.),(50.,50.,50.)))
        self.assertEqual(reason,'');self.assertEqual(len(line['points']),2)
        line,reason=route(start,end,tube,obstacles=(((-.001,-5.,-5.),(.001,5.,5.)),))
        self.assertIsNone(line);self.assertEqual(reason,'tube_route_obstructed')
        edge=dict(start,position=(-46.,0.,0.))
        line,reason=route(edge,end,tube,case_bounds=((-50.,-50.,-50.),(50.,50.,50.)))
        self.assertIsNone(line);self.assertEqual(reason,'tube_route_outside_case')
        carbon=dict(tube,material='carbon',tube_type='hard')
        line,reason=route(dict(start,normal=(0.,1.,0.)),end,carbon)
        self.assertIsNone(line);self.assertEqual(reason,'rigid_tube_requires_inline_elbows')

    def test_a_real_existing_mesh_is_avoided_and_an_enclosed_endpoint_cancels_all_routes(self):
        from assembly_geometry import Mesh,box
        from liquid_routes046 import bounds_intersection
        _,healthy=self.build();line=healthy['selected_loop']['routes'][0]
        center=line['points'][len(line['points'])//2]
        obstacle=Mesh('synthetic-existing-pcb',box(8.,8.,8.),(.15,.2,.25,1.),center,'board')
        meshes,meta=self.build(meshes=(obstacle,))
        self.assertTrue(meta['selected_loop']['connected_reference_loop'])
        bounds=(tuple(v-4 for v in center),tuple(v+4 for v in center))
        radius=self.references[TUBING]['tube_outer_mm']/2
        for route in meta['selected_loop']['routes']:
            self.assertTrue(all(not bounds_intersection(a,b,bounds,radius) for a,b in zip(route['points'],route['points'][1:])))
        # An already enclosed CPU endpoint has no safe escape in any direction.
        blocked=Mesh('synthetic-enclosed-socket',box(130.,130.,130.),(.15,.2,.25,1.),ANCHORS['cpu']['position'],'cpu')
        meshes,meta=self.build(meshes=(blocked,))
        self.assert_disconnected(meshes,meta,'tube_route_obstructed')

    def test_both_actual_cfrp_skus_require_straight_inline_connections(self):
        start=dict(position=(-40.,0.,0.),normal=(1.,0.,0.));end=dict(position=(40.,0.,0.),normal=(-1.,0.,0.))
        for identity in ('alphacool-carbon-13-10','alphacool-carbon-16-13'):
            tubing=get_component('tubing',identity)
            self.assertEqual(tubing['material'],'CFRP')
            self.assertEqual(tubing['geometry_family'],'carbon_hard_tube')
            straight,reason=route(start,end,tubing)
            self.assertEqual(reason,'');self.assertEqual(len(straight['points']),2)
            curved,reason=route(dict(start,normal=(0.,1.,0.)),end,tubing)
            self.assertIsNone(curved);self.assertEqual(reason,'rigid_tube_requires_inline_elbows')

    def test_each_entire_routed_tube_has_exactly_two_open_outer_boundary_rings(self):
        meshes,meta=self.build();tubes=[m for m in meshes if m.name=='loop-reference-routed-tube']
        self.assertEqual(len(tubes),3)
        for mesh in tubes:
            edges=Counter()
            for at in range(0,len(mesh.vertices),18):
                triangle=[tuple(round(v,6) for v in mesh.vertices[at+j:at+j+3]) for j in (0,6,12)]
                for a,b in zip(triangle,(*triangle[1:],triangle[0])):edges[tuple(sorted((a,b)))]+=1
            boundary=[pair for pair,count in edges.items() if count==1]
            self.assertTrue(boundary)
            self.assertEqual(len(boundary),12)  # six-sided eco cross-section at two ends
            self.assertTrue(all(count in (1,2) for count in edges.values()))
            graph={}
            for a,b in boundary:graph.setdefault(a,set()).add(b);graph.setdefault(b,set()).add(a)
            self.assertTrue(all(len(neighbors)==2 for neighbors in graph.values()))
            left=set(graph);rings=[]
            while left:
                pending=[left.pop()];ring=set(pending)
                while pending:
                    for node in graph[pending.pop()]:
                        if node in left:left.remove(node);ring.add(node);pending.append(node)
                rings.append(ring)
            self.assertEqual(sorted(map(len,rings)),[6,6])

    def test_per_end_override_has_exact_identity_and_removal_leaves_no_hanging_half_tubes(self):
        row=copy.deepcopy(self.references[FITTING]);row.update(id='fixture-port-override',label='Synthetic override fixture')
        source=self.scratch/'override.dspack';source.write_bytes(packs.make_pack('test-loop046-port','Port fixture',[wrapper(row)],kind='loop'))
        self.store.install(source)
        value=spec(loop_fittings={'cpu_block_model:port1':row['id']})
        meshes,meta=self.build(value);self.assertTrue(meta['selected_loop']['connected_reference_loop'])
        chosen=next(p for p in meta['parts'] if p.get('attached_port_key')=='cpu_block_model:port1')
        self.assertEqual(chosen['model_id'],row['id'])
        self.assertTrue(self.store.remove('test-loop046-port'));self.assertEqual(get_component('fitting',row['id']),{})
        meshes,meta=self.build(value);self.assert_disconnected(meshes,meta,'unknown_loop_component')
        self.assertFalse(any(p.get('model_id')==row['id'] for p in meta['parts']))
        self.assertTrue(get_component('cpu_block',BLOCK))
        self.assertTrue(self.store.remove('test-loop046'));self.assertEqual(get_component('cpu_block',BLOCK),{})
        meshes,meta=self.build();self.assert_disconnected(meshes,meta,'unknown_loop_component')
        self.assertEqual(meta['selected_loop']['stock_model_id'],'')

    def test_actual_full_scene_and_all_thirteen_styles_share_part_geometry_without_author_imports(self):
        value=spec();value.update(case=dict(layout='tower',dimensions_mm=dict(width=600.,height=800.,depth=800.)),memory=dict(count=0),detail_level='eco')
        scene=build_scene(value);loop=scene.metadata['cooling']['selected_loop']
        self.assertEqual(len(loop['routes']),3)
        selected=tuple(m for m in scene.meshes if m.part_id.startswith('cooler:'))
        self.assertTrue(selected)
        physical=lambda meshes:[(m.name,m.vertices,m.position,m.component,m.rotor,m.direction,m.axis,m.part_id) for m in meshes]
        expected=physical(selected)
        for style in HARDWARE_ICON_STYLES:
            styled,meta=apply_model_styles(selected,style,{},scene.dimensions,{'front':'open'})
            self.assertEqual(physical(styled),expected,style)
            self.assertTrue(all(a.vertices is b.vertices for a,b in zip(selected,styled)))
            self.assertEqual(set(meta['mesh_style_ids']),{style})
        mixed,meta=apply_model_styles(selected,'miniature',{'cooler:cpu':'notebook_line','cooler:pump-reservoir':'cartoon'},scene.dimensions,{'front':'open'})
        self.assertEqual(physical(mixed),expected)
        self.assertTrue(any(s=='notebook_line' for m,s in zip(mixed,meta['mesh_style_ids']) if m.part_id=='cooler:cpu'))
        self.assertFalse(any(m.name.startswith('style-') for m in mixed))


if __name__=='__main__':unittest.main()
