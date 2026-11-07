"""Synthetic data-only renderer boundaries; no catalog or device discovery."""
import copy
import importlib
import json
import unittest
from unittest.mock import patch

import cooling_pack_schema045 as schema
from hardware_packs import PackError


URL='https://example.test/manufacturer/spec'


def fan():
    return dict(id='test-fan-120',label='Example fan 120',brand='Example',series='Reference',sources=[URL],
        family='arctic-pressure',size_mm=120,width_mm=120,depth_mm=25,blades=5,shape='wide',frame='square',
        frame_color='#20272d',blade_color='#343d43',hub_ratio=.25,pads=False,rgb=False,outer_ring=False,
        dimensions_verified=False,blade_count_verified=False,mount_pitch_mm=None,mount_pitch_verified=False,
        rotation_direction_verified=False,geometry_accuracy='original_reference')


def cooler():
    return dict(id='test-cooler',label='Example cooler',brand='Example',series='Reference',sources=[URL],
        kind='single_tower',fan_count=1,fan_model='test-fan-120',fan_reference_mm=120,
        dimensions_mm=dict(width=125,height=158,depth=112),dimensions_verified=False,heatpipes=6,
        heatpipe_count_verified=False,bundled_fan_reference=fan())


def radiator():
    return dict(id='test-radiator',label='Example radiator',brand='Example',series='Reference',sources=[URL],
        category='radiator',selection_source='manual',loop_type='custom',dimensions_mm=dict(length=396,width=120,thickness=30),
        fan_size_mm=120,fan_count=3,fan_mount_capacity_per_side=3,fan_mount_sides=2,fan_mount_pitch_mm=None,
        fan_mount_pitch_verified=False,ports_count=2,active_port_count=2,port_thread='G1/4',port_layout='unknown',
        ports=[],ports_geometry_complete=False,shell_family='corsair_xr_frame',shell_features=[],materials={},
        fpi=None,fin_count=None,fpi_verified=False,fan_count_is_installed=False,live_temperature_available=False)


def wrapper(kind,reference=None):
    reference=copy.deepcopy(reference or {'fan':fan,'cooler':cooler,'radiator':radiator}[kind]())
    if kind=='fan':selector=dict(size_mm=reference['size_mm'],depth_mm=reference['depth_mm'],frame=reference['frame'],
        frameless=reference.get('frameless',False),mount_pitch_mm=reference.get('mount_pitch_mm'),mount_pitch_verified=reference.get('mount_pitch_verified',False))
    elif kind=='cooler':selector=dict(kind=reference['kind'],fan_size_mm=reference.get('fan_reference_mm',reference.get('fan_size_mm')))
    else:selector={key:reference[key] for key in ('fan_size_mm','fan_count','fan_mount_pitch_mm','fan_mount_pitch_verified')}
    return dict(id=reference['id'],label=reference['label'],vendor=reference['brand'],series=reference['series'],
        aliases=[reference['label']],sources=copy.deepcopy(reference['sources']),reference=reference,selector=selector)


class CoolingPackSchemaTests(unittest.TestCase):
    def test_custom_loop_requires_its_own_reservoir_geometry_and_identity(self):
        row=cooler();row.update(kind='custom_loop',fan_count=3,radiator_size=360,
            radiator_mm=dict(length=396,width=120,thickness=30),pump_style='xc7_block',
            pump_reference_mm=dict(width=87,height=36,depth=78),
            reservoir_mm=dict(diameter=60,height=200),reservoir_model='Explicit reference tank')
        self.assertTrue(schema.validate_model('cooler',wrapper('cooler',row)))
        for field in ('reservoir_mm','reservoir_model'):
            broken=copy.deepcopy(row);broken.pop(field)
            with self.assertRaises(PackError):schema.validate_model('cooler',wrapper('cooler',broken))

    def test_three_kinds_have_detached_picker_summary_and_preserve_unknowns(self):
        for kind in schema.KINDS:
            value=wrapper(kind);before=copy.deepcopy(value)
            result=schema.validate_model(kind,value);summary=schema.summary_for(kind,value)
            self.assertEqual(value,before);self.assertEqual(result,before)
            self.assertEqual(set(summary),{'id','label','vendor','series','aliases','selector'})
            self.assertEqual(schema.validate_summary(kind,summary),summary)
            result['reference']['sources'].clear();summary['aliases'].clear()
            self.assertEqual(value,before)
            self.assertEqual(json.loads(json.dumps(before)),before)
        self.assertIsNone(schema.validate_model('fan',wrapper('fan'))['reference']['mount_pitch_mm'])
        self.assertFalse(schema.validate_model('fan',wrapper('fan'))['reference']['blade_count_verified'])
        self.assertIsNone(schema.validate_model('radiator',wrapper('radiator'))['reference']['fin_count'])

    def test_identity_sources_selector_and_exact_fields_cannot_disagree(self):
        for kind in schema.KINDS:
            for mutate in (lambda x:x.update(id='different'),lambda x:x.update(vendor='different'),
                           lambda x:x.update(label='different'),lambda x:x.update(series='different'),
                           lambda x:x.update(sources=['https://other.test/spec']),lambda x:x.update(code='execute'),
                           lambda x:x['reference'].update(asset_path='C:/arbitrary'),
                           lambda x:x['reference'].update(renderer='arbitrary')):
                row=wrapper(kind);mutate(row)
                with self.subTest(kind=kind,mutation=repr(row)),self.assertRaises(PackError):schema.validate_model(kind,row)
            row=wrapper(kind);row['selector'][next(iter(row['selector']))]='spoofed'
            with self.assertRaises(PackError):schema.validate_model(kind,row)
            for invalid in (None,[],False,{'id':'incomplete'}):
                with self.assertRaises(PackError):schema.validate_model(kind,invalid)
        for kind in (None,[],False,'cpu','../fan'):
            with self.assertRaises(PackError):schema.validate_summary(kind,{})

    def test_numeric_bounds_reject_bool_nonfinite_huge_and_unbounded_lists(self):
        mutations=(lambda x:x.update(blades=0),lambda x:x.update(blades=65),lambda x:x.update(blades=True),
                   lambda x:x.update(size_mm=float('nan')),lambda x:x.update(width_mm=float('inf')),
                   lambda x:x.update(depth_mm=10**1000),lambda x:x.update(hub_ratio=.9),
                   lambda x:x.update(hub_display_resolution=[2,2,2]),lambda x:x.update(rgb='true'),
                   lambda x:x.update(shape='execute'),lambda x:x.update(frame_color='url(https://bad.test)'))
        for mutate in mutations:
            row=wrapper('fan');mutate(row['reference'])
            with self.assertRaises(PackError):schema.validate_model('fan',row)
        for field,value in (('ports',[{}]*17),('dimensions_mm',dict(length=100000,width=120,thickness=30)),
                            ('materials',dict(renderer='python')),('shell_features',['unknown-template'])):
            row=wrapper('radiator');row['reference'][field]=value
            with self.assertRaises(PackError):schema.validate_model('radiator',row)

    def test_nested_bundled_fan_is_single_depth_and_bound_to_actual_model_and_size(self):
        row=wrapper('cooler');out=schema.validate_model('cooler',row)
        self.assertEqual(out['reference']['bundled_fan_reference']['id'],out['reference']['fan_model'])
        for mutate in (lambda x:x.update(fan_model=None),lambda x:x.update(fan_reference_mm=140),
                       lambda x:x['bundled_fan_reference'].update(id='different'),
                       lambda x:x['bundled_fan_reference'].update(bundled_fan_reference=fan()),
                       lambda x:x['bundled_fan_reference'].update(sources=['file:///bad']),
                       lambda x:x['bundled_fan_reference'].update(depth_mm=100000)):
            row=wrapper('cooler');mutate(row['reference'])
            with self.assertRaises(PackError):schema.validate_model('cooler',row)
        row=wrapper('cooler');del row['reference']['fan_reference_mm']
        with self.assertRaises(PackError):schema.validate_model('cooler',row)

    def test_qualitative_foil_is_bounded_and_never_a_custom_renderer(self):
        reference=fan();reference.update(family='new-color-family',foil_profile=dict(sweep_deg=20,leading=.2,trailing=.3,root=.25),foil_profile_accuracy='qualitative_reference')
        self.assertEqual(schema.validate_model('fan',wrapper('fan',reference))['reference']['foil_profile'],reference['foil_profile'])
        for key,value in (('sweep_deg',56),('leading',.6),('root',.1),('trailing',True),('script','bad')):
            row=wrapper('fan',reference);row['reference']['foil_profile'][key]=value
            with self.assertRaises(PackError):schema.validate_model('fan',row)
        for mutate in (lambda x:x.pop('foil_profile_accuracy'),lambda x:x.pop('foil_profile'),
                       lambda x:x.update(foil_profile_accuracy='manufacturer_CAD'),lambda x:x.update(family='../renderer')):
            row=wrapper('fan',reference);mutate(row['reference'])
            with self.assertRaises(PackError):schema.validate_model('fan',row)

    def test_mount_axes_keep_unknown_orientation_and_missing_verified_numbers_fail(self):
        reference=fan();reference.update(mount_pitch_axes_mm=[93.,83.],mount_pitch_axes_verified=True,
            mount_pitch_axes_orientation_verified=False,mounting_source=URL)
        out=schema.validate_model('fan',wrapper('fan',reference))
        self.assertIsNone(out['reference']['mount_pitch_mm']);self.assertFalse(out['reference']['mount_pitch_axes_orientation_verified'])
        for mutate in (lambda x:x.update(mount_pitch_axes_mm=[93]),lambda x:x.update(mount_pitch_axes_mm=[0,83]),
                       lambda x:x.pop('mounting_source'),lambda x:x.update(mount_pitch_verified=True)):
            row=wrapper('fan',reference);mutate(row['reference'])
            with self.assertRaises(PackError):schema.validate_model('fan',row)
        row=wrapper('fan');row['reference'].update(mount_pitch_axes_orientation_verified=True)
        with self.assertRaises(PackError):schema.validate_model('fan',row)

    def test_no_installed_inference_live_telemetry_or_exact_unknown_internals(self):
        for kind,fields in (('radiator',('aio_replacement_verified','fan_count_is_installed','mounting_positions_verified',
                'port_positions_verified','default_caps_installed','shell_geometry_verified','internal_channels_verified',
                'live_flow_available','live_temperature_available','installed_hardware_inferred')),
                ('cooler',('gpu_block','internal_vrm_impeller_verified','pump_axis_orientation_verified'))):
            for field in fields:
                row=wrapper(kind);row['reference'][field]=True
                with self.subTest(kind=kind,field=field),self.assertRaises(PackError):schema.validate_model(kind,row)
        for field,value in (('fpi_verified',True),('ports_geometry_complete',True),('fin_count',500),
                            ('fan_mount_capacity_per_side',4),('port_layout_verified',True)):
            row=wrapper('radiator');row['reference'][field]=value
            with self.assertRaises(PackError):schema.validate_model('radiator',row)

    def test_ports_are_bounded_structural_evidence_not_script_or_unverified_CAD(self):
        port=dict(id='connection-1',face='front',position_normalized=[-.28,.455,.5],role='connection',positions_verified=False,source=URL)
        row=wrapper('radiator');row['reference']['ports']=[port]
        self.assertEqual(schema.validate_model('radiator',row)['reference']['ports'],[port])
        for mutation in ({'positions_verified':True},{'position_normalized':[1,0,0]},{'end':1},
                         {'face':'custom-mesh'},{'source':'javascript:bad'},{'code':'bad'}):
            value=copy.deepcopy(row);value['reference']['ports'][0].update(mutation)
            with self.assertRaises(PackError):schema.validate_model('radiator',value)
        value=copy.deepcopy(row);value['reference']['ports']*=2
        with self.assertRaises(PackError):schema.validate_model('radiator',value)

    def test_text_url_alias_limits_and_summary_do_not_allow_reference_payload(self):
        for field,value in (('aliases',['same','same']),('aliases',['x']*9),('label','x'*257),
                            ('vendor','<script>'),('series','line\nbreak'),('sources',['https://user:pass@example.test/'])):
            row=wrapper('fan');row[field]=value
            with self.assertRaises(PackError):schema.validate_model('fan',row)
        summary=schema.summary_for('fan',wrapper('fan'));summary['reference']=fan()
        with self.assertRaises(PackError):schema.validate_summary('fan',summary)
        for kind,flag in (('fan','mount_pitch_verified'),('radiator','fan_mount_pitch_verified')):
            summary=schema.summary_for(kind,wrapper(kind));summary['selector'][flag]=True
            with self.assertRaises(PackError):schema.validate_summary(kind,summary)

    def test_synthetic_models_cross_real_archive_boundary_without_runtime_catalogs(self):
        from hardware_packs import make_pack,_archive
        for kind in schema.KINDS:
            value=wrapper(kind)
            raw=make_pack('test-'+kind,'Synthetic '+kind,[value],kind=kind)
            manifest,models=_archive(raw)
            self.assertEqual(manifest['kind'],kind)
            self.assertEqual(manifest['products'],[schema.summary_for(kind,value)])
            self.assertEqual(models,[schema.validate_model(kind,value)])

    def test_fresh_schema_import_and_validation_do_not_load_catalogs_or_devices(self):
        import builtins
        real_import=builtins.__import__;seen=[]
        def guarded(name,*args,**kwargs):
            seen.append(name)
            if any(word in name for word in ('catalog','expansion','PySide','assembly_')):raise AssertionError(name)
            return real_import(name,*args,**kwargs)
        with (patch('builtins.__import__',side_effect=guarded),patch('ctypes.WinDLL',side_effect=AssertionError('device')),
              patch('subprocess.Popen',side_effect=AssertionError('process')),patch('threading.Thread.start',side_effect=AssertionError('worker'))):
            importlib.reload(schema)
            for kind in schema.KINDS:self.assertTrue(schema.validate_model(kind,wrapper(kind)))
        self.assertFalse(any('catalog' in name for name in seen))


if __name__=='__main__':unittest.main()
