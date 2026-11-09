"""Exact Fractal thin shells/inlays; pure geometry, no devices or renderer."""
from collections import Counter,defaultdict
import copy
import math
import unittest
from unittest.mock import patch

from assembly_geometry import Mesh,Scene,box,build_scene
from assembly_shroud_fractal052 import CASE_IDS,build,finish,layout_reference
from assembly_auxiliary import _segment_triangle
from assembly_style import apply_model_styles
from assembly_visibility048 import mesh_visible
from chassis_catalog import CASES,get_case

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def dimensions(case):return tuple(float(case['dimensions_mm'][k]) for k in ('width','height','depth'))


def triangles(mesh):
    return tuple(tuple(tuple(mesh.vertices[i+j+k]+mesh.position[k] for k in range(3))
                 for j in (0,6,12)) for i in range(0,len(mesh.vertices),18))


def hit(mesh,a,b):return any(_segment_triangle(a,b,t) for t in triangles(mesh))


def bounds(mesh):
    return tuple(tuple(op(mesh.vertices[k::6])+mesh.position[k] for k in range(3)) for op in (min,max))


class FractalShroud052Tests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure geometry; no native/window/worker')))

    def test_exact_three_products_and_detached_source_reference_fields(self):
        self.assertEqual(len(CASE_IDS),3)
        for case in CASES:
            before=copy.deepcopy(case);meshes,meta=build(case,dimensions(case),(.1,.2,.3,1.))
            self.assertEqual(case,before)
            if case['id'] not in CASE_IDS:
                self.assertEqual((meshes,meta),((),{}));continue
            self.assertTrue(meshes);self.assertFalse(meta['cad_verified']);self.assertFalse(meta['dimensions_verified'])
            self.assertFalse(meta['thickness_verified']);self.assertFalse(meta['positions_verified'])
            self.assertFalse(meta['selected_component_geometry_used']);self.assertFalse(meta['far_side_wall_added'])
            self.assertFalse(meta['chamber_is_solid']);self.assertFalse(meta['exact_vent_pattern_modeled'])
            self.assertEqual({m.part_id for m in meshes},{r['id'] for r in meta['parts']})
            self.assertTrue(all(m.name=='psu-shroud' and m.component=='case' for m in meshes))
            self.assertTrue(all(r['kind']=='case_cover' and r['assembly_state']=='installed' for r in meta['parts']))
            self.assertTrue(all(r['source_url'].startswith('https://www.fractal-design.com/') for r in meta['parts']))
            meta['parts'][0]['label']='mutated detached result'
            self.assertNotEqual(build(case,dimensions(case),(.1,.2,.3,1.))[1]['parts'][0]['label'],meta['parts'][0]['label'])
        for invalid in ((True,469.,447.),(215.,float('nan'),447.),(215.,469.),(215.,469.,0.)):
            self.assertEqual(build(get_case(CASE_IDS[0]),invalid,(0,0,0,1)),((),{}))

    def test_all_material_bodies_are_closed_connected_positive_thickness_and_normal_consistent(self):
        for case_id in CASE_IDS:
            meshes,_=build(get_case(case_id),dimensions(get_case(case_id)),(.1,.2,.3,1.))
            for mesh in meshes:
                edges=Counter();direction=Counter();adjacency=defaultdict(set);edge_faces=defaultdict(list);volume=0.
                for i,t in enumerate(triangles(mesh)):
                    a,b,c=t;ab=tuple(b[k]-a[k] for k in range(3));ac=tuple(c[k]-a[k] for k in range(3))
                    normal=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                    self.assertGreater(math.hypot(*normal),1e-7)
                    stored=mesh.vertices[i*18+3:i*18+6]
                    self.assertAlmostEqual(sum(x*x for x in stored),1.)
                    self.assertGreater(sum(normal[k]*stored[k] for k in range(3)),0.)
                    volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
                    for p,q in zip(t,(*t[1:],t[0])):
                        key=tuple(sorted((p,q)));edges[key]+=1;direction[key]+=1 if p<q else -1;edge_faces[key].append(i)
                self.assertEqual(set(edges.values()),{2},case_id)
                self.assertEqual(set(direction.values()),{0},case_id)
                self.assertGreater(volume,1.);self.assertLess(volume,250000.)
                for faces in edge_faces.values():
                    a,b=faces;adjacency[a].add(b);adjacency[b].add(a)
                visited=set();pending=[0]
                while pending:
                    i=pending.pop()
                    if i not in visited:visited.add(i);pending.extend(adjacency[i]-visited)
                self.assertEqual(len(visited),mesh.vertex_count//3)

    def test_real_empty_compartment_keeps_side_roof_and_north_specific_front_step(self):
        for case_id in CASE_IDS:
            case=get_case(case_id);w,h,d=dimensions(case);meshes,meta=build(case,(w,h,d),(.1,.2,.3,1.))
            main=meshes[0];top=meta['roof_world_y_mm'];side=-(w-12.)/2;rear=-(d-12.)/2
            self.assertFalse(hit(main,(-w*.3,-h*.43,0.),(w*.3,-h*.43,0.)))
            self.assertFalse(hit(main,(w*.45,-h*.43,0.),(w*.49,-h*.43,0.)))
            self.assertTrue(hit(main,(side-2,-h*.43,0.),(side+3,-h*.43,0.)))
            self.assertTrue(hit(main,(0.,top-3,rear+40),(0.,top+3,rear+40)))
            # In front of the fixed main deck there is no invented full-width
            # bottom roof. Installed removable inlays are separate solids.
            z=(meta['normalized_reference']['roof_end_depth_fraction']*d+(d-12.)/2)/2
            self.assertFalse(hit(main,(0.,top-3,z),(0.,top+3,z)))
            if case_id=='fractal-north-mesh':
                self.assertEqual(len(meshes),1);self.assertFalse(meta['deferred_part_ids'])
                self.assertTrue(meta['relief_profile_world_zy_mm'])
                self.assertFalse(hit(main,(side-2,top-5,z),(side+3,top-5,z)))
                self.assertTrue(hit(main,(side-2,top-h*.06-3,z),(side+3,top-h*.06-3,z)))
            else:
                self.assertEqual(len(meshes),3);self.assertEqual(len(meta['deferred_part_ids']),2)
                self.assertTrue(all(r['factory_removable'] for r in meta['parts'][1:]))

    def test_inlays_removed_only_by_actual_front_material_not_request_wire_or_empty_bbox(self):
        case=get_case('fractal-define-7-compact-solid');meshes,meta=build(case,dimensions(case),(.1,.2,.3,1.))
        row=meta['parts'][-1];lo,hi=(row['reference_bounds_world_mm'][k] for k in ('min','max'))
        center=tuple((lo[k]+hi[k])/2 for k in range(3));owner='fans:front:0'
        actual=Mesh('case-fan-rigid-reference',box(100.,20.,20.),(.1,.2,.3,1.),center,'fans',part_id=owner)
        part=dict(id=owner,kind='case_fan',mount='front',model_id='source-observed-reference')
        before=copy.deepcopy(meta)
        for parts,physical in (([part],()),([], (actual,)),([dict(part,mount='top')],(actual,)),
                               ([part],(Mesh('case-fan-wire',actual.vertices,actual.color,center,'fans',part_id=owner),))):
            result,state=finish(meshes,physical,dict(parts=parts),meta)
            self.assertEqual(result,meshes);self.assertEqual(state['removed_parts'],[])
        # A hollow frame with an overlapping outer box but its material wholly
        # outside this inlay's X range is not an occupancy witness.
        left=Mesh('empty-box-proxy-left',box(1.,20.,20.),actual.color,(-200.,center[1],center[2]),'fans',part_id=owner)
        right=Mesh('empty-box-proxy-right',left.vertices,left.color,(200.,center[1],center[2]),'fans',part_id=owner)
        result,state=finish(meshes,(left,right),dict(parts=[part]),meta)
        self.assertEqual(result,meshes);self.assertFalse(state['removed_parts'])
        result,state=finish((*meshes,actual),(actual,),dict(parts=[part]),meta)
        self.assertNotIn(row['id'],{m.part_id for m in result})
        self.assertIn('case:psu-cover',{m.part_id for m in result});self.assertIn(actual,result)
        self.assertEqual(state['removed_parts'][0]['reason'],'front_inlay_removed_for_fan_or_radiator_space')
        self.assertFalse(state['removed_parts'][0]['physical_mesh_present']);self.assertEqual(meta,before)
        # Independent radiator fans intentionally have no mount field. Their
        # exact parent ID must still permit the documented inlay removal when
        # only the deeper fan, not its tank, enters that material slab.
        parent='cooler:radiator';fan='cooler:radiator:front:0'
        tank=Mesh('actual-tank-outside-inlay',box(100.,20.,5.),actual.color,(center[0],center[1]+40,center[2]),'cooler',part_id=parent)
        inner=Mesh('cooler-radiator-fan-frame',actual.vertices,actual.color,center,'cooler',part_id=fan)
        declared=[dict(id=parent,kind='radiator',mount='front'),dict(id=fan,kind='radiator_fan',radiator_part_id=parent)]
        kept,removed=finish(meshes,(tank,inner),dict(parts=declared),meta)
        self.assertEqual(removed['removed_parts'][0]['proof']['part_id'],fan)
        for missing in ((inner,),(tank,)):
            kept,unrelated=finish(meshes,missing,dict(parts=declared),meta)
            self.assertEqual(kept,meshes);self.assertEqual(unrelated['removed_parts'],[])

    def test_actual_front_fans_three_lods_keep_declared_whole_groups_without_material_crossing(self):
        # Test actual producer geometry, not envelope counts or a single mock
        # fan. A retained cover's rigid skin regions are independently bounded.
        for case_id in CASE_IDS:
            case=get_case(case_id);w,h,d=dimensions(case)
            for model,size in (('arctic-p12-pwm',120),('arctic-p14-pwm',140)):
                count=next(m['count'] for m in case['fan_mounts'] if m['position']=='front' and size in m['size_mm'])
                for level in ('eco','balanced','close'):
                    scene=build_scene(dict(case=case,detail_level=level,memory=dict(count=0),
                        cooling=dict(case_fans=[dict(model=model,mount='front',count=count,direction='intake')])))
                    fans=[r for r in scene.metadata['cooling']['parts'] if r.get('kind')=='case_fan' and r.get('mount')=='front']
                    self.assertEqual(len(fans),count,(case_id,model,level,scene.metadata['cooling'].get('rejected')))
                    covers=[m for m in scene.meshes if m.part_id.startswith('case:psu-')]
                    self.assertTrue(covers)
                    frames=[m for m in scene.meshes if m.name=='case-fan-frame' and m.part_id in {r['id'] for r in fans}]
                    self.assertEqual(len(frames),count)
                    # No fan can reach the thin side skin. The fixed rear
                    # deck's front edge is behind every front rigid frame.
                    main=next(m for m in covers if m.part_id=='case:psu-cover')
                    side=-(w-12.)/2;end=scene.metadata['case_shroud']['normalized_reference']['roof_end_depth_fraction']*d
                    for fan in frames:
                        lo,hi=bounds(fan);self.assertGreater(lo[0],side+1.2);self.assertGreater(lo[2],end)
                    # Every retained detachable top slab is strictly separated
                    # along at least one actual frame axis; occupied ones have
                    # been removed whole before hardware/anchors are indexed.
                    for cover in (m for m in covers if m is not main):
                        low,high=bounds(cover)
                        for fan in frames:
                            a,b=bounds(fan)
                            self.assertTrue(any(high[k]<=a[k]+1e-7 or b[k]<=low[k]+1e-7 for k in range(3)),(case_id,model,cover.part_id))
                    self.assertEqual({r['id'] for r in scene.metadata['case_shroud']['parts']},{m.part_id for m in covers})
                    self.assertFalse({r['id'] for r in scene.metadata['case_shroud']['removed_parts']} & {m.part_id for m in scene.meshes})

    def test_front_radiator_inlay_state_uses_actual_built_identity_and_preserves_main(self):
        for case_id in CASE_IDS:
            case=get_case(case_id)
            for level in ('eco','balanced','close'):
                scene=build_scene(dict(case=case,detail_level=level,memory=dict(count=0),
                    cooling=dict(cpu_cooler='arctic-liquid-freezer-iii-360',radiator_mount='front')))
                radiators=[r for r in scene.metadata['cooling']['parts'] if r.get('kind')=='radiator']
                self.assertEqual(len(radiators),1,(case_id,scene.metadata['cooling']))
                state=scene.metadata['case_shroud']
                self.assertEqual(bool(state['removed_parts']),case_id!='fractal-north-mesh')
                self.assertIn('case:psu-cover',{m.part_id for m in scene.meshes})
                self.assertTrue(all(r['proof']['part_id'] in {x['id'] for x in radiators} for r in state['removed_parts']))
                self.assertFalse(any(m.part_id in {r['id'] for r in state['removed_parts']} for m in scene.meshes))
                # The complete front stack, not only the radiator tank, must
                # remain in front of the fixed main roof. The former North
                #.34D reference cut through the lowest fan's rigid frame.
                end=scene.dimensions[2]*state['normalized_reference']['roof_end_depth_fraction']
                frames=[m for m in scene.meshes if m.name=='cooler-radiator-fan-frame']
                self.assertTrue(frames)
                self.assertGreater(min(bounds(m)[0][2] for m in frames),end)

    def test_six_styles_share_physical_source_and_psu_visibility_contract(self):
        for case_id in CASE_IDS:
            case=get_case(case_id);dims=dimensions(case);meshes,meta=build(case,dims,(.1,.2,.3,1.))
            for style in SIX:
                styled,_=apply_model_styles(meshes,style,{},dims,case.get('panels',{}))
                covers=[m for m in styled if m.part_id in {p.part_id for p in meshes}]
                self.assertEqual(len(covers),len(meshes))
                for source,actual in zip(meshes,covers):
                    self.assertIs(source.vertices,actual.vertices);self.assertEqual(source.position,actual.position)
                    self.assertEqual(source.part_id,actual.part_id)
                    for cutaway in (False,True):
                        self.assertTrue(mesh_visible(actual,cutaway,False));self.assertFalse(mesh_visible(actual,cutaway,True))

    def test_actual_atx_power_supply_clears_floor_and_cover_and_pcb_is_above_not_cut(self):
        from assembly_case_shrouds052 import apply_layout_anchors
        for case_id in CASE_IDS:
            case=get_case(case_id);w,h,d=dimensions(case);layout=layout_reference(case,(w,h,d))
            self.assertEqual(layout['psu']['floor_y_mm'],-h/2+20.)
            self.assertEqual(layout['board_y_mm'],h*.10)
            self.assertFalse(layout['psu_fan_orientation_verified'])
            # The supply's derived center uses its real dimensions; fixed
            # cover/host coordinates are independent of that selection.
            spec=dict(case=case,auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024')))
            anchors=apply_layout_anchors({},spec,layout)
            self.assertEqual(anchors['psu']['world_dimensions_mm'],(150.,86.,160.))
            self.assertEqual(anchors['psu']['position'],(0.,-h/2+63.,-d/2+90.))
            for level in ('eco','balanced','close'):
                scene=build_scene(dict(spec,detail_level=level,memory=dict(count=2)))
                psu=[m for m in scene.meshes if m.part_id=='psu:0'];self.assertTrue(psu)
                actual_low=tuple(min(bounds(m)[0][k] for m in psu) for k in range(3))
                actual_high=tuple(max(bounds(m)[1][k] for m in psu) for k in range(3))
                floor=next(m for m in scene.meshes if m.name=='case-bottom')
                self.assertGreater(actual_low[1]-bounds(floor)[1][1],.5)
                covers=[m for m in scene.meshes if m.part_id.startswith('case:psu-')]
                roof_inside=scene.metadata['case_shroud']['roof_world_y_mm']-1.2
                self.assertGreater(roof_inside-actual_high[1],5.)
                # All actual PSU pieces, including fasteners and label/knob,
                # are separated from the viewing-side skin in full X extent.
                self.assertGreater(actual_low[0],-(w-12.)/2+1.2)
                pcb=next(m for m in scene.meshes if m.name=='motherboard-reference')
                self.assertGreater(bounds(pcb)[0][1],scene.metadata['case_shroud']['roof_world_y_mm'])
                # Contacts with the real floor are not hidden by an empty
                # bay AABB. The side skin itself ends on the floor's top.
                self.assertAlmostEqual(bounds(covers[0])[0][1],bounds(floor)[1][1])

    def test_source_top_limits_use_radiator_rails_without_repositioning_ordinary_case_fans(self):
        from assembly_case_shrouds052 import apply_layout_anchors
        from assembly_cooling import add_cooling
        for case_id in CASE_IDS:
            case=get_case(case_id);dims=dimensions(case);layout=layout_reference(case,dims)
            for height in (31.25,44.,None):
                # This synthetic dimension-contract check supplements the
                # independent actual-native KVR control; it does not purport
                # to generate a model-specific RAM profile.
                module={} if height is None else dict(height_mm=height)
                spec=dict(case=case,memory=dict(count=1,modules=[module]),
                    cooling=dict(cpu_cooler='arctic-liquid-freezer-iii-240',radiator_mount='top'))
                before=copy.deepcopy(spec);anchors=apply_layout_anchors(dict(case_dimensions=dims),spec,layout)
                meshes,meta=add_cooling((),spec,'eco',anchors)
                check=meta['case_radiator_limit_checks'][0]
                if height==44. and case_id!='fractal-meshify-2-light-tg':
                    self.assertEqual(meta['rejected'][0]['reason'],'radiator_memory_height_exceeds_case_limit')
                    self.assertEqual(meshes,());self.assertEqual(meta['parts'],[])
                else:
                    frames=[m for m in meshes if m.name=='cooler-radiator-fan-frame']
                    self.assertEqual(len(frames),2)
                    for m in frames:self.assertAlmostEqual(sum(bounds(m)[i][0] for i in (0,1))/2,-dims[0]*.16)
                    if height is None and case_id!='fractal-meshify-2-light-tg':
                        self.assertEqual(check['state'],'reference_dimension_unknown')
                        self.assertEqual(check['unknown_ram_heights'],1)
                self.assertEqual(spec,before)
            for size,model in ((120,'arctic-p12-pwm'),(140,'arctic-p14-pwm')):
                spec=dict(case=case,cooling=dict(cpu_cooler='none',case_fans=[dict(model=model,mount='top',count=2)]))
                anchors=apply_layout_anchors(dict(case_dimensions=dims),spec,layout)
                meshes,meta=add_cooling((),spec,'eco',anchors)
                frames=[m for m in meshes if m.name=='case-fan-frame']
                self.assertEqual(len(frames),2)
                for m in frames:self.assertAlmostEqual(sum(bounds(m)[i][0] for i in (0,1))/2,0.)


if __name__=='__main__':unittest.main()
