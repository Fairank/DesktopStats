"""Mechanical/motion contracts for the explicit cooling reference builder."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_cooling import add_cooling
from cooling_catalog import choices_coolers,choices_fans,get_cooler,get_fan


ANCHORS={'cpu':{'position':(-35.,35.,10.),'normal':(-1.,0.,0.),'up':(0.,1.,0.)},
         'case_dimensions':(600.,800.,800.)}


def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _dot(a,b):return sum(a[i]*b[i] for i in range(3))
def _sub(a,b):return tuple(a[i]-b[i] for i in range(3))


def _hit(vertices,origin,direction):
    for i in range(0,len(vertices),18):
        a,b,c=(vertices[i+k:i+k+3] for k in (0,6,12))
        e1,e2=_sub(b,a),_sub(c,a);h=_cross(direction,e2);det=_dot(e1,h)
        if abs(det)<1e-9:continue
        inv=1/det;s=_sub(origin,a);u=inv*_dot(s,h)
        if not 0<=u<=1:continue
        q=_cross(s,e1);v=inv*_dot(direction,q)
        if v<0 or u+v>1:continue
        if inv*_dot(e2,q)>1e-7:return True
    return False


class CoolingCatalogTests(unittest.TestCase):
    def test_sources_and_dimensions_are_explicit(self):
        self.assertEqual(len(choices_coolers()),26)
        self.assertEqual(len(choices_fans()),26)
        self.assertEqual({get_fan(c['id'])['size_mm'] for c in choices_fans()},{80,92,120,140,160,180,200})
        for choice in choices_coolers():
            row=get_cooler(choice['id']);self.assertTrue(row['sources']);self.assertEqual(row['reviewed'],'2026-11-07')
            self.assertTrue(row['brand']);self.assertTrue(row['series'])
            self.assertTrue(all(url.startswith('https://') for url in row['sources']))
        self.assertEqual(get_cooler('noctua-nh-d15')['dimensions_mm']['height'],165)
        self.assertEqual(get_cooler('noctua-nh-d15-g2')['dimensions_mm']['height'],168)
        self.assertFalse(get_cooler('amd-wraith-stealth')['dimensions_verified'])
        self.assertTrue(get_cooler('intel-laminar-rm1')['envelope_is_upper_bound'])
        self.assertFalse(get_fan('lian-li-lancool-216-160')['dimensions_verified'])
        self.assertFalse(get_fan('lian-li-lancool-216-160')['outer_ring'])
        self.assertFalse(get_cooler('custom-loop-360-reference')['gpu_block'])

    def test_getters_are_detached_and_invalid_ids_are_empty(self):
        row=get_cooler('noctua-nh-d15');row['sources'].clear();row['dimensions_mm']['height']=1
        self.assertEqual(get_cooler('noctua-nh-d15')['dimensions_mm']['height'],165)
        self.assertTrue(get_cooler('noctua-nh-d15')['sources'])
        self.assertEqual(get_cooler([]),{});self.assertEqual(get_fan('unknown'),{})
        row=get_fan('arctic-p12-pwm');row['sources'].clear();self.assertTrue(get_fan(row['id'])['sources'])


class CoolingGeometryTests(unittest.TestCase):
    def test_default_unknown_never_invents_parts(self):
        for spec in ({},None,{'cooling':{}},{'cooling':{'cpu_cooler':'none'}}):
            meshes,meta=add_cooling((),spec,anchors=ANCHORS)
            self.assertEqual(meshes,());self.assertEqual(meta['parts'],[]);self.assertFalse(meta['cpu_fan_tach_usable'])
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'not-real'}})
        self.assertEqual(meshes,());self.assertEqual(meta['rejected'][0]['reason'],'unknown_model')

    def test_no_io_workers_or_input_mutation(self):
        spec={'cooling':{'cpu_cooler':'arctic-liquid-freezer-iii-360','case_fans':[{'model':'arctic-p12-pwm','mount':'side','count':3}]}}
        original=copy.deepcopy((spec,ANCHORS))
        with patch('subprocess.Popen',side_effect=AssertionError('no process')),patch('threading.Thread.start',side_effect=AssertionError('no thread')),patch('builtins.open',side_effect=AssertionError('no file IO')):
            meshes,meta=add_cooling((),spec,anchors=ANCHORS)
        self.assertTrue(meshes);self.assertEqual((spec,ANCHORS),original);self.assertEqual(meta['new_pollers'],0)

    def test_all_catalog_models_all_levels_are_finite_normalized_bounded(self):
        for level in ('eco','balanced','close'):
            for choice in choices_coolers():
                with self.subTest(level=level,model=choice['id']):
                    meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':choice['id']}},level,ANCHORS)
                    self.assertTrue(meshes);self.assertFalse(meta['rejected']);self.assertLess(meta['triangle_count'],30000)
                    self._validate_meshes(meshes)
            for choice in choices_fans():
                with self.subTest(level=level,fan=choice['id']):
                    meshes,meta=add_cooling((),{'cooling':{'case_fans':[{'model':choice['id'],'mount':'front','count':1}]}},level,ANCHORS)
                    self.assertTrue(meshes);self.assertLess(meta['triangle_count'],6000);self._validate_meshes(meshes)

    def _validate_meshes(self,meshes):
        for mesh in meshes:
            self.assertIn(mesh.component,('cooler','fans'));self.assertTrue(mesh.part_id.startswith(mesh.component+':'))
            self.assertEqual(len(mesh.vertices)%18,0);self.assertTrue(all(math.isfinite(v) for v in mesh.vertices))
            for i in range(0,len(mesh.vertices),6):
                self.assertTrue(all(abs(mesh.vertices[i+k])<1500 for k in range(3)))
                self.assertAlmostEqual(sum(mesh.vertices[i+k]**2 for k in (3,4,5)),1,places=5)
            if mesh.rotor:self.assertIn('leaves-hub',mesh.name)

    def test_actual_frames_have_open_central_apertures(self):
        spec={'cooling':{'case_fans':[{'model':'arctic-p12-pwm','mount':'front','count':1}]}}
        meshes,meta=add_cooling((),spec,anchors=ANCHORS)
        fan=meta['fans'][0];center=fan['position'];axis=fan['axis']
        origin=tuple(center[i]+axis[i]*100 for i in range(3));direction=tuple(-v for v in axis)
        frames=[m for m in meshes if m.name=='case-fan-frame']
        self.assertEqual(len(frames),1);self.assertFalse(_hit(frames[0].vertices,origin,direction))
        self.assertTrue(_hit(frames[0].vertices,(center[0]+56,center[1]+45,origin[2]),direction))

    def test_mount_direction_axes_and_stators_remain_separate(self):
        for mount,normal in {'front':(0,0,1),'rear':(0,0,-1),'top':(0,1,0),'bottom':(0,-1,0),'side':(1,0,0)}.items():
            for direction,sign in (('intake',1),('exhaust',-1)):
                meshes,meta=add_cooling((),{'cooling':{'case_fans':[{'model':'arctic-p12-pwm','mount':mount,'count':1,'direction':direction}]}},anchors=ANCHORS)
                rotor=[m for m in meshes if m.rotor];self.assertEqual(len(rotor),1)
                self.assertEqual(rotor[0].axis,tuple(v*sign for v in normal));self.assertEqual(meta['fans'][0]['rpm'],None)
                self.assertTrue(any('stator' in m.name and not m.rotor for m in meshes))
                self.assertTrue(all(not m.rotor for m in meshes if 'frame' in m.name or 'pads' in m.name))

    def test_case_known_mount_limits_and_no_silent_truncation(self):
        anchors=copy.deepcopy(ANCHORS);anchors['case']={'fan_mounts':[{'position':'front','count':2,'size_mm':[120]}]}
        for model,count in (('noctua-nf-a14-pwm',1),('arctic-p12-pwm',3),('arctic-p12-pwm',True),('arctic-p12-pwm',0)):
            meshes,meta=add_cooling((),{'cooling':{'case_fans':[{'model':model,'mount':'front','count':count}]}},anchors=anchors)
            self.assertEqual(meshes,());self.assertTrue(meta['rejected'])
        meshes,meta=add_cooling((),{'cooling':{'case_fans':[{'model':'arctic-p12-pwm','mount':'front','count':2}]}},anchors=anchors)
        self.assertEqual(len(meta['fans']),2);self.assertEqual(len({f['part_id'] for f in meta['fans']}),2)

    def test_reference_preset_counts_no_duplicate_radiator_mount(self):
        spec={'cooling':{'cpu_cooler':'arctic-liquid-freezer-iii-360','radiator_mount':'top','case_fans':[
            {'model':'arctic-p12-pwm','mount':'side','count':3},{'model':'arctic-p12-pwm','mount':'bottom','count':3},
            {'model':'arctic-p12-pwm','mount':'rear','count':1},{'model':'arctic-p12-pwm','mount':'top','count':3}]}}
        meshes,meta=add_cooling((),spec,anchors=ANCHORS)
        self.assertEqual(sum(f['role']=='case' for f in meta['fans']),7)
        self.assertEqual(sum(f['role']=='radiator' for f in meta['fans']),3)
        self.assertEqual(sum(f['role']=='vrm_independent' for f in meta['fans']),1)
        self.assertEqual(meta['rejected'][0]['reason'],'radiator_occupies_mount')
        self.assertLess(meta['triangle_count'],45000)
        self.assertFalse(meta['cpu_fan_tach_usable']);self.assertEqual(meta['real_cpu_rotor_parts'],[])

    def test_sensor_semantics_air_header_not_aio_pump_or_vrm(self):
        for choice in choices_coolers():
            _,meta=add_cooling((),{'cooling':{'cpu_cooler':choice['id']}},anchors=ANCHORS)
            air=choice['kind'] not in ('aio','custom_loop')
            self.assertEqual(meta['cpu_fan_tach_usable'],air)
            reviewed=get_fan(get_cooler(choice['id']).get('fan_model')).get('blade_geometry_reviewed',False)
            self.assertEqual(meta['real_cpu_rotor_parts'],['cooler:cpu'] if air and reviewed else [])
            self.assertIn('representative' if air else 'pump',meta['fan_tach_mapping'])

    def test_posed_cpu_normal_is_used_exactly_once(self):
        anchors=copy.deepcopy(ANCHORS);anchors['cpu']={'position':(50,40,30),'normal':(0,1,0),'up':(0,0,1)}
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'noctua-nh-l9i-17xx'}},anchors=anchors)
        fan=next(m for m in meshes if m.rotor);self.assertEqual(fan.axis,(0.,1.,0.))
        self.assertGreater(fan.position[1],40);self.assertAlmostEqual(fan.position[0],50);self.assertAlmostEqual(fan.position[2],30)

    def test_custom_loop_has_real_categories_and_no_gpu_block(self):
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'custom-loop-360-reference'}},anchors=ANCHORS)
        self.assertEqual({p['kind'] for p in meta['parts']},{'radiator','pump_reservoir','cpu_waterblock'})
        self.assertTrue(any('liquid-tubes' in m.name for m in meshes));self.assertTrue(any('d5-pump' in m.name for m in meshes))
        self.assertFalse(any(m.component=='gpu' or 'gpu-block' in m.name for m in meshes))

    def test_reservoir_glass_and_fluid_remain_transparent_across_styles(self):
        from assembly_style import apply_model_styles
        from top_bar_config import HARDWARE_ICON_STYLES
        meshes,_=add_cooling((),{'cooling':{'cpu_cooler':'custom-loop-360-reference'}},anchors=ANCHORS)
        expected={'cooler-reservoir-shell':.22,'cooler-reservoir-fluid-core':.55,
                  'cooler-reservoir-caps':1.,'cooler-d5-pump':1.,'cooler-reservoir-clamps':1.}
        for entry in HARDWARE_ICON_STYLES:
            style=entry[0] if isinstance(entry,(tuple,list)) else entry
            styled,_=apply_model_styles(meshes,style,{},ANCHORS['case_dimensions'],{})
            actual={m.name:m.color[3] for m in styled if m.name in expected}
            self.assertEqual(actual,expected,style)

    def test_explicit_gpu_block_replaces_only_on_success_with_two_distinct_radiators(self):
        anchors=copy.deepcopy(ANCHORS);anchors['gpu']={'pcb':dict(position=(-40,-50,20),width_mm=140,length_mm=300,normal=(0,-1,0),up=(1,0,0))}
        spec={'cooling':{'cpu_cooler':'custom-loop-360-reference','gpu_waterblock':True,'case_fans':[dict(model='arctic-p12-pwm',mount='side',count=3)]}}
        meshes,meta=add_cooling((),spec,anchors=anchors)
        self.assertTrue(meta['replace_gpu_cooler']);self.assertEqual(meta['secondary_radiator_mount'],'side')
        self.assertEqual(sum(p['kind']=='radiator' for p in meta['parts']),2)
        block=[m for m in meshes if m.part_id=='gpu:waterblock'];self.assertTrue(block)
        self.assertTrue(all(m.component=='gpu' and not m.rotor for m in block))
        self.assertTrue(any(m.color[3]<1 for m in block));self.assertEqual(meta['rejected'][0]['reason'],'radiator_occupies_mount')
        spec['cooling']['radiator_mount']='side';_,meta=add_cooling((),spec,anchors=anchors)
        self.assertTrue(meta['replace_gpu_cooler']);self.assertEqual(meta['secondary_radiator_mount'],'top')
        _,meta=add_cooling((),spec,anchors=ANCHORS)
        self.assertFalse(meta['replace_gpu_cooler']);self.assertTrue(any('original GPU cooler retained' in w for w in meta['warnings']))

    def test_attached_power_wires_avoid_invented_argb_or_controller(self):
        spec={'cooling':{'cpu_cooler':'noctua-nh-u12a','case_fans':[dict(model='arctic-p12-pwm',mount='front',count=2)]}}
        meshes,meta=add_cooling((),spec,anchors=ANCHORS)
        self.assertEqual(len(meta['wire_anchors']),4)
        self.assertTrue(all(a['kind']=='fan4' and a['header']=='fan' and a['connector_rendered'] for a in meta['wire_anchors']))
        self.assertTrue(all(a['position_verified'] is False for a in meta['wire_anchors']))
        self.assertTrue(all(any(m.part_id==a['owner'] and 'power-connector' in m.name for m in meshes) for a in meta['wire_anchors']))

    def test_lfiii_primary_crown_replaces_generic40mm_axial_reference(self):
        row=get_cooler('arctic-liquid-freezer-iii-360')
        self.assertEqual(row['pump_reference_mm'],dict(width=91,height=68.5,depth=108.5))
        self.assertEqual(row['vrm_fan_diameter_mm'],60)
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':row['id']}},anchors=ANCHORS)
        crown=[m for m in meshes if m.name=='cooler-lfiii-static-radial-crown'];self.assertEqual(len(crown),1)
        self.assertFalse(crown[0].rotor)
        self.assertTrue(any(m.name=='cooler-lfiii-twin-hose-elbows' and not m.rotor for m in meshes))
        self.assertTrue(any(m.name=='cooler-lfiii-undercut-cheeks' for m in meshes))
        vrm=next(f for f in meta['fans'] if f['role']=='vrm_independent')
        self.assertEqual(vrm['diameter_mm'],60);self.assertFalse(vrm['blade_count_verified'])
        self.assertFalse(meta['cpu_fan_tach_usable']);self.assertEqual(meta['real_cpu_rotor_parts'],[])

    def test_rear_fan_lead_can_exit_glass_side_without_moving_verified_fan(self):
        for mount in ('rear','bottom'):
            spec={'cooling':{'case_fans':[dict(model='arctic-p12-pwm',mount=mount,count=1,direction='exhaust')]}}
            meshes,meta=add_cooling((),spec,anchors=ANCHORS)
            self.assertEqual(meta['fans'][0]['position'][0],0)
            anchor=meta['wire_anchors'][0]
            self.assertLess(anchor['position'][0],-60)
            self.assertEqual(anchor['normal'],(-1.,0.,0.))
            self.assertFalse(anchor['position_verified'])
            self.assertTrue(any(m.rotor and m.position==meta['fans'][0]['position'] for m in meshes))

    def test_source_side_mount_uses_outward_face_and_inward_actual_thickness(self):
        anchors=copy.deepcopy(ANCHORS);anchors['case_dimensions']=(320,470,470)
        anchors['case_mount_planes']={'side':dict(position=(108.8,0,108.1),normal=(1,0,0),up=(0,1,0),source='official-manual-reference',method='observed_proportions')}
        meshes,meta=add_cooling((),{'cooling':{'case_fans':[dict(model='arctic-p12-pwm',mount='side',count=3)]}},anchors=anchors)
        frames=[m for m in meshes if m.name=='case-fan-frame'];self.assertEqual(len(frames),3)
        self.assertAlmostEqual(max(v+m.position[0] for m in frames for v in m.vertices[0::6]),108.8)
        self.assertAlmostEqual(min(v+m.position[0] for m in frames for v in m.vertices[0::6]),83.8)
        self.assertFalse(meta['mount_plane_sources']['side']['dimensions_verified'])
        meshes,meta=add_cooling((),{'cooling':{'cpu_cooler':'arctic-liquid-freezer-iii-360','radiator_mount':'side'}},anchors=anchors)
        rails=[m for m in meshes if m.name=='cooler-radiator-rails']
        self.assertAlmostEqual(max(v+m.position[0] for m in rails for v in m.vertices[0::6]),108.8)
        self.assertTrue(all(f['position'][0]<108.8-38 for f in meta['fans'] if f['role']=='radiator'))

    def test_known_raised_deck_moves_reference_reservoir_without_scaling(self):
        anchors=copy.deepcopy(ANCHORS);anchors['case_dimensions']=(320,470,470)
        anchors['case_floor_deck']=dict(position=(-61.5,-190,0),normal=(0,1,0),thickness_mm=2)
        spec={'cooling':{'cpu_cooler':'custom-loop-360-reference'}}
        meshes,meta=add_cooling((),spec,anchors=anchors)
        pump=[m for m in meshes if m.name=='cooler-d5-pump']
        self.assertEqual(len(pump),1)
        lower=min(pump[0].vertices[1::6])+pump[0].position[1]
        self.assertAlmostEqual(lower,-187.)
        self.assertEqual(meta['cooler']['reservoir_mm']['height'],200)


if __name__=='__main__':unittest.main()
