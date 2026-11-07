"""Independent radiators/fans preserve geometry, hardware identity and no fake telemetry."""
import copy
import unittest
from unittest.mock import patch

from assembly_config import validate_assembly
from assembly_cooling import add_cooling
from assembly_inspection import snapshot
from assembly_parts import selected_parts,fit_messages
from assembly_style import apply_model_styles
from cooling_catalog import get_cooler,get_fan
from liquid_cooling_catalog044 import records,get_radiator
from liquid_selection044 import resolve_liquid_choices
from tests.test_assembly_cooling import ANCHORS
from top_bar_config import HARDWARE_ICON_STYLES


class ModularLiquidTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No hardware or background work')))

    def spec(self,**updates):
        options=validate_assembly(dict(cooler_model='custom-loop-360-reference',**updates))
        return selected_parts(options)

    def test_all_exact_radiators_can_be_inspected_without_fans_in_all_styles(self):
        for row in records():
            spec=self.spec(radiator_model=row['id'],radiator_fan_layout='none')
            before=copy.deepcopy(spec)
            meshes,meta=add_cooling((),spec,'eco',ANCHORS)
            self.assertEqual(spec,before)
            self.assertFalse(meta['rejected'],(row['id'],meta['rejected']))
            part=next(p for p in meta['parts'] if p['kind']=='radiator')
            self.assertEqual(part['model_id'],row['id'])
            self.assertEqual(part['dimensions_mm'],row['dimensions_mm'])
            self.assertEqual(meta['radiator_fan_count'],0)
            self.assertFalse(any(m.rotor for m in meshes))
            for style in HARDWARE_ICON_STYLES:
                result,_=apply_model_styles(meshes,style,{},ANCHORS['case_dimensions'],{'front':'open'})
                self.assertEqual(len(result),len(meshes))
                self.assertTrue(all(a.vertices is b.vertices for a,b in zip(meshes,result)))

    def test_push_pull_fans_are_independent_selectable_and_share_throughflow_axis(self):
        spec=self.spec(radiator_model='corsair-xr5-360',radiator_fan_model='noctua-nf-a12x25-pwm',radiator_fan_layout='push_pull')
        meshes,meta=add_cooling((),spec,'balanced',ANCHORS)
        self.assertFalse(meta['rejected'])
        fans=[p for p in meta['parts'] if p['kind']=='radiator_fan']
        self.assertEqual(len(fans),6);self.assertEqual(len({p['id'] for p in fans}),6)
        self.assertEqual({p['model_id'] for p in fans},{'noctua-nf-a12x25-pwm'})
        self.assertTrue(all(p['id'].startswith('cooler:radiator:') for p in fans))
        self.assertFalse(any(m.rotor and m.part_id=='cooler:radiator' for m in meshes))
        self.assertEqual({f['axis'] for f in meta['fans'] if f['role']=='radiator'},{(0.,-1.,0.)})
        # Single-instance overrides never repaint neighboring fans or the shell.
        result,info=apply_model_styles(meshes,'miniature',{fans[0]['id']:'notebook_line'},ANCHORS['case_dimensions'],{})
        styled=[s for m,s in zip(result,info['mesh_style_ids']) if m.part_id==fans[0]['id']]
        self.assertTrue(styled);self.assertEqual(set(styled),{'notebook_line'})
        self.assertEqual({s for m,s in zip(result,info['mesh_style_ids']) if m.part_id=='cooler:radiator'},{'miniature'})
        self.assertTrue(all('cooler:radiator'!=f['part_id'] for f in meta['fans']))

    def test_invalid_fan_size_or_mounts_do_not_create_a_half_assembled_cooler(self):
        for identity in ('noctua-nf-a14-pwm','not-registered'):
            meshes,meta=add_cooling((),self.spec(radiator_model='corsair-xr5-360',radiator_fan_model=identity),anchors=ANCHORS)
            self.assertFalse(meshes);self.assertTrue(meta['rejected'])
        _,meta=add_cooling((),self.spec(radiator_model='xspc-ex280',radiator_fan_model='noctua-nf-a15-pwm'),anchors=ANCHORS)
        self.assertIn('radiator_fan_mount_requires_review',{r['reason'] for r in meta['rejected']})
        self.assertEqual(get_fan('noctua-nf-a15-pwm')['mount_pitch_mm'],105.)
        self.assertEqual(get_fan('noctua-nf-a14-pwm')['mount_pitch_mm'],124.5)

    def test_aio_keeps_factory_radiator_and_secondary_selection_is_independent(self):
        aio=get_cooler('arctic-liquid-freezer-iii-360');before=copy.deepcopy(aio)
        primary,secondary,issues=resolve_liquid_choices(aio,dict(radiator_model='corsair-xr7-360'))
        self.assertEqual(primary['radiator_mm'],aio['radiator_mm'])
        self.assertIn('aio_radiator_is_fixed',{r['reason'] for r in issues});self.assertEqual(aio,before)
        base=get_cooler('custom-loop-360-reference')
        a,b,issues=resolve_liquid_choices(base,dict(gpu_waterblock=True,radiator_model='corsair-xr5-240',secondary_radiator_model='alphacool-xt45-v2-280',secondary_radiator_fan_model='noctua-nf-a14-pwm'))
        self.assertFalse(issues)
        self.assertEqual(a['_radiator_profile']['id'],'corsair-xr5-240')
        self.assertEqual(b['_radiator_profile']['id'],'alphacool-xt45-v2-280')
        self.assertEqual(a['fan_count'],2);self.assertEqual(b['fan_reference_mm'],140)

    def test_inspection_never_assigns_cpu_temperature_or_header_rpm_to_radiator_parts(self):
        spec=self.spec(radiator_model='corsair-xr5-360',radiator_fan_model='arctic-p12-pwm')
        _,meta=add_cooling((),spec,'eco',ANCHORS)
        for part in (p for p in meta['parts'] if p['kind'] in ('radiator','radiator_fan','pump_reservoir')):
            result=snapshot(dict(time=100,cpu_temp=70,cpu_fan_rpm=900),spec,{},part['id'],now=100,scene_metadata=dict(cooling=meta))
            self.assertEqual(result['identity'],part['label'])
            self.assertFalse(any(r.get('metric') in ('cpu_temp','cpu_fan_rpm') for r in result['rows']))
            self.assertFalse(any('RPM' in r['value'] for r in result['rows']))

    def test_no_fan_inspection_ignores_unused_fan_conflicts_and_preserves_the_preference(self):
        options=validate_assembly(dict(cooler_model='custom-loop-360-reference',radiator_model='alphacool-xt45-v2-280',
            radiator_fan_layout='none',radiator_fan_model='noctua-nf-a12x25-pwm'))
        before=copy.deepcopy(options)
        meshes,meta=add_cooling((),selected_parts(options),'eco',ANCHORS)
        self.assertEqual(options,before)
        self.assertFalse(meta['rejected']);self.assertTrue(meshes)
        self.assertEqual(meta['radiator_fan_count'],0)
        self.assertEqual(meta['radiators'][0]['model_id'],'alphacool-xt45-v2-280')

    def test_unknown_standalone_port_positions_never_acquire_fake_aio_hoses(self):
        for identity in ('ek-quantum-surface-s240','hardwarelabs-nemesis-360gtx'):
            spec=self.spec(radiator_model=identity,radiator_fan_layout='none')
            meshes,meta=add_cooling((),spec,'eco',ANCHORS)
            self.assertTrue(any(p['model_id']==identity for p in meta['parts']))
            self.assertFalse(any(m.name in ('cooler-radiator-fittings','cooler-radiator-reference-hose-collars','cooler-liquid-tubes') for m in meshes))
            self.assertEqual(meta['connection_issues'][0]['model_id'],identity)
            self.assertFalse(meta['radiators'][0]['hose_connections_ready'])

    def test_small_published_pitch_difference_is_review_not_incompatibility(self):
        spec=self.spec(radiator_model='xspc-ex280',radiator_fan_model='noctua-nf-a14-pwm')
        meshes,meta=add_cooling((),spec,'eco',ANCHORS)
        self.assertTrue(meshes);self.assertFalse(meta['rejected'])
        self.assertEqual(meta['radiator_fan_count'],2)
        self.assertEqual(meta['mounting_issues'][0]['radiator_pitch_mm'],125)
        self.assertEqual(meta['mounting_issues'][0]['fan_pitch_mm'],124.5)
        self.assertIn('风扇标称孔距与冷排不同，安装间隙待核。',fit_messages(spec,dict(cooling=meta)))


if __name__=='__main__':unittest.main()
