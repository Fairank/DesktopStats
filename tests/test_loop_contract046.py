"""Strict external data, static readouts and honest partial-loop messages."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import hardware_packs as packs
from liquid_pack_schema046 import validate_model,validate_reference,validate_summary,summary_for
from tools.export_loop_packs046 import pack_models,export


class LoopContract046Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.models=pack_models()

    def test_all_six_discriminators_and_detached_index_have_no_geometry_payload(self):
        kinds=set()
        for raw in self.models:
            before=copy.deepcopy(raw);row=validate_model(raw);kinds.add(row['reference']['part_kind'])
            summary=summary_for(row)
            self.assertEqual(set(summary),{'id','label','vendor','series','aliases','selector'})
            self.assertEqual(set(summary['selector']),{'part_kind','form'})
            self.assertEqual(validate_summary(summary),summary)
            row['reference']['ports'].clear();summary['aliases'].clear()
            self.assertEqual(raw,before)
        self.assertEqual(kinds,{'cpu_block','pump','reservoir','pump_reservoir','fitting','tubing'})

    def test_data_cannot_smuggle_renderers_live_values_or_unbounded_geometry(self):
        base=copy.deepcopy(self.models[0])
        mutations=[lambda r:r.update(script='run'),lambda r:r['reference'].update(vertices=[0]*9),
            lambda r:r['reference'].update(live_temperature_available=True),
            lambda r:r['reference'].update(geometry_family=[]),lambda r:r['reference'].update(form={}),
            lambda r:r['reference']['reference_envelope_mm'].update(width=float('nan')),
            lambda r:r['reference']['reference_envelope_mm'].update(height=True),
            lambda r:r['reference']['reference_envelope_mm'].update(depth=801),
            lambda r:r['reference'].update(geometry_features=['x']*25),
            lambda r:r['reference'].update(ports=r['reference']['ports']*25),
            lambda r:r['reference']['ports'][0].update(position_verified=True),
            lambda r:r['reference']['ports'][0].update(position_normalized=[.51,0,0]),
            lambda r:r['reference']['ports'][0].update(thread='M20',role='inlet'),
            lambda r:r['reference']['ports'][0].update(face='angled',normal_reference=[1,1,1]),
            lambda r:r['reference']['axis_verified'].update(width=True) or r['reference']['dimensions_mm'].update(width=None),
            lambda r:r['selector'].update(part_kind='pump',form='cpu_block'),
            lambda r:r['selector'].update(form=[])]
        for mutate in mutations:
            row=copy.deepcopy(base);mutate(row)
            with self.subTest(row=repr(row)[:250]),self.assertRaises(packs.PackError):validate_model(row)

    def test_motor_bare_top_and_tank_identities_cannot_be_interchanged(self):
        for raw in self.models:
            ref=raw['reference'];kind=ref['part_kind']
            if kind=='reservoir':changes={'contains_motor':True}
            elif kind=='pump':changes={'contains_motor':not ref['contains_motor']}
            else:continue
            bad=copy.deepcopy(ref);bad.update(changes)
            with self.subTest(id=ref['id']),self.assertRaises(packs.PackError):validate_reference(bad)

    def test_export_is_deterministic_immutable_and_alternative_groups_not_extra_products(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);first=export(root);before={p.name:p.read_bytes() for p in root.iterdir()}
            self.assertEqual(export(root),first)
            self.assertEqual({p.name:p.read_bytes() for p in root.iterdir()},before)
            all_ids=set()
            self.assertEqual(len({Path(p['file']).name for p in first['packs']}),len(first['packs']))
            for pack in first['packs']:
                # In-workspace exports use repository-relative manifest paths;
                # isolated tests deliberately place their temp files there.
                reported=Path(pack['file']);filename=reported.name
                actual=(Path(__file__).resolve().parents[1]/reported if reported.parent!=Path('.') else root/reported)
                self.assertEqual(actual.resolve(),(root/filename).resolve())
                payload=before[filename]
                self.assertEqual(len(payload),pack['bytes'])
                self.assertEqual(hashlib.sha256(payload).hexdigest(),pack['sha256'])
                manifest,rows=packs._archive(payload)
                self.assertEqual(manifest['kind'],'loop');all_ids.update(r['id'] for r in rows)
            self.assertEqual(len(all_ids),first['unique_products'])
            self.assertEqual(first['unique_products'],63)
            damaged=next(root.iterdir());damaged.write_bytes(b'previous published bytes')
            with self.assertRaises(FileExistsError):export(root)
            self.assertEqual(damaged.read_bytes(),b'previous published bytes')

    def test_actual_pack_readouts_never_relabel_cpu_values_as_coolant_flow_or_pump_speed(self):
        from assembly_inspection import snapshot
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);source=root/'fixture.dspack'
            source.write_bytes(packs.make_pack('readout-loop','Readout fixture',self.models,kind='loop'))
            store=packs.PackStore(root/'installed');store.install(source)
            with patch.object(packs,'_store',store):
                for raw in self.models:
                    row=raw['reference'];part=dict(id='cooler:selected',kind=row['part_kind'],model_id=row['id'],label=row['label'])
                    result=snapshot(dict(time=1,cpu_temp=91,cpu_fan_rpm=1900,cpu_usage=100),
                        dict(cpu=dict(telemetry_bound=False)),{},'cooler:selected',now=100,
                        scene_metadata=dict(cooling=dict(parts=[part])))
                    self.assertEqual(result['identity'],row['label']);self.assertLessEqual(len(result['rows']),6)
                    self.assertFalse(any(r.get('metric') for r in result['rows']))
                    for r in result['rows']:
                        if r['label'] in ('水温','水泵转速','流量'):self.assertFalse(r['available'])
                    self.assertNotIn('读数已过期',result['notes'])
                    self.assertNotIn('参考型号未绑定本机传感器。',result['notes'])
                missing=dict(id='cooler:selected',kind='cpu_block',model_id='removed-block',label='Removed')
                result=snapshot({}, {}, {},'cooler:selected',now=100,scene_metadata=dict(cooling=dict(parts=[missing])))
                self.assertEqual(result['state'],'unavailable')
                self.assertEqual(result['rows'][0]['reason'],'对应扩展包未安装或型号已移除。')

    def test_known_errors_and_unknown_reviews_both_reach_the_fit_panel(self):
        from assembly_parts import fit_messages
        from liquid_messages046 import REASONS
        meta=dict(cooling=dict(loop_issues=[dict(reason='port_thread_or_gender_unknown')],
            rejected=[dict(kind='loop_component',reason='cpu_block_socket_unsupported')]))
        result=fit_messages({},meta)
        self.assertEqual(result,[REASONS['port_thread_or_gender_unknown'],REASONS['cpu_block_socket_unsupported']])
        self.assertEqual(fit_messages({},{}),[])

    def test_grouped_picker_scans_one_small_index_without_loading_selected_payloads(self):
        from liquid_component_runtime046 import grouped_choices,get_component
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);source=root/'fixture.dspack'
            source.write_bytes(packs.make_pack('picker-loop','Picker fixture',self.models,kind='loop'))
            store=packs.PackStore(root/'installed');store.install(source)
            with patch.object(packs,'_store',store),patch.object(store,'choices',wraps=store.choices) as read:
                grouped=grouped_choices()
                self.assertEqual(read.call_count,1)
                self.assertEqual(sum(map(len,grouped.values())),63)
                self.assertEqual(store.memory_status()['selected_records'],0)
                row=grouped['cpu_block'][0];identity=row['id'];row['label']='mutated'
                actual=get_component('cpu_block',identity);actual['ports'].clear()
                self.assertTrue(get_component('cpu_block',identity)['ports'])
                self.assertNotEqual(grouped_choices()['cpu_block'][0]['label'],'mutated')


if __name__=='__main__':unittest.main()
