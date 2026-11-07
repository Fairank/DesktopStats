"""Cached component selection never probes, borrows sensors or changes models."""
import copy
import unittest
from unittest.mock import patch

from assembly_inspection import COMPONENT_LABELS,snapshot
from assembly_spec import build_spec
from stats_config import DEFAULT


class AssemblyInspectionTests(unittest.TestCase):
    def setUp(self):
        for path in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(path,side_effect=AssertionError('Presentation performs no I/O')))
        self.enterContext(patch('top_bar_feedback.time.time',return_value=100.0))
        self.config=copy.deepcopy(DEFAULT)
        self.config['assembly']['case_model']='hyte-y60'
        self.config['top_bar']['items']=[dict(metric='gpu_usage',prefs=dict(
            gpu_target='1',hardware_model='asus-astral-5090'))]
        self.data=dict(time=100.0,cpu_name='Intel Core i7-13700KF',cpu_usage=23,cpu_temp=61.5,
            cpu_power=74.3,cpu_frequency=4.2,ram_percent=37.5,ram_used_gb=24,
            ram_available_gb=40,ram_total_gb=64,metric_timestamps={'cpu_temp':100.0},
            gpus={'0':dict(gpu_name='Other card',gpu_temp=99,gpu_usage=100),
                  '1':dict(gpu_name='RTX 5090',gpu_temp=42,gpu_usage=30,gpu_power=180,
                      gpu_clock=2200,vram_percent=25,gpu_fan_rpm=1480,gpu_fan_rpm_timestamp=100.0,
                      gpu_fan_rpm_source='NVIDIA NVML',gpu_fan_rpm_scope='card',
                      gpu_fan_rpm_semantics='driver_current_rpm',
                      channel_status={'gpu_fan_rpm':dict(state='available',aggregate='mean')})})
        firmware=dict(state='available',baseboards=[dict(manufacturer='ASUSTeK COMPUTER INC.',
            product='ROG STRIX Z790-A GAMING WIFI D4')])
        self.spec=build_spec(self.data,self.config,firmware,[])

    def inspect(self,component='all',**kwargs):
        return snapshot(self.data,self.spec,self.config,component,now=100.0,**kwargs)

    def test_all_components_offer_bounded_rows_and_keep_every_input_unchanged(self):
        before=copy.deepcopy((self.data,self.spec,self.config))
        for component in COMPONENT_LABELS:
            with self.subTest(component=component):
                result=self.inspect(component)
                self.assertEqual(result['component'],component)
                self.assertTrue(1<=len(result['rows'])<=6)
                self.assertTrue(all(isinstance(row['value'],str) for row in result['rows']))
        self.assertEqual((self.data,self.spec,self.config),before)

    def test_selected_gpu_keeps_exact_card_readings_and_measured_rpm(self):
        result=self.inspect('gpu');rows={row['metric']:row for row in result['rows']}
        self.assertEqual(self.spec['gpu']['target'],'1')
        self.assertEqual(rows['gpu_temp']['value'],'42 °C')
        self.assertEqual(rows['gpu_fan_rpm']['value'],'1480 RPM')
        self.assertIn('风扇转速为板卡汇总读数。',result['notes'])
        del self.data['gpus']['1'];self.data.update(gpu_temp=88,gpu_fan_rpm=3000)
        self.assertTrue(all(not row['available'] for row in self.inspect('gpu')['rows']))

    def test_verified_factory_counts_are_static_facts_and_unknown_models_add_none(self):
        board={row['label']:row for row in self.inspect('board')['rows']}
        self.assertEqual(board['DIMM 插槽']['value'],'4')
        self.assertEqual(board['M.2 插槽']['value'],'4')
        case={row['label']:row for row in self.inspect('case')['rows']}
        self.assertEqual(case['原厂前置 USB']['value'],'A × 2 · C × 1')
        self.assertEqual(case['原厂音频接口']['value'],'1')
        self.spec['board'].pop('slot_counts')
        self.spec['case'].pop('exterior_details')
        self.assertNotIn('DIMM 插槽',{row['label'] for row in self.inspect('board')['rows']})
        self.assertNotIn('原厂前置 USB',{row['label'] for row in self.inspect('case')['rows']})

    def test_channel_failure_blocks_cached_numeric_and_nonfinite_or_boolean_values_are_gaps(self):
        self.data['gpus']['1']['channel_status']['gpu_temp']=dict(state='unavailable')
        rows={row['metric']:row for row in self.inspect('gpu')['rows']}
        self.assertEqual(rows['gpu_temp']['value'],'—')
        self.assertTrue(rows['gpu_usage']['available'])
        for field,value in (('cpu_usage',True),('cpu_temp',float('nan')),
                            ('cpu_power',float('inf')),('cpu_frequency',False)):
            self.data[field]=value
        self.assertTrue(all(not row['available'] for row in self.inspect('cpu')['rows'] if row.get('metric')))

    def test_whole_sample_and_cpu_source_timestamps_expire_independently(self):
        self.data['metric_timestamps']['cpu_temp']=90.0
        rows={row['metric']:row for row in self.inspect('cpu')['rows'] if row.get('metric')}
        self.assertFalse(rows['cpu_temp']['available']);self.assertTrue(rows['cpu_usage']['available'])
        self.data['time']=101.0
        self.assertTrue(all(not row['available'] for row in self.inspect('all')['rows']))
        self.data['time']=64.0
        self.assertIn('读数已过期',self.inspect()['notes'])
        self.assertTrue(all(not row['available'] for row in self.inspect()['rows']))

    def test_exact_gpu_channel_timestamp_overrides_a_fresh_frame_and_rejects_invalid_or_future_times(self):
        channel=dict(state='available',timestamp=100.0)
        self.data['gpus']['1']['channel_status']['gpu_temp']=channel
        self.data['metric_timestamps']['gpu_temp']=100.0
        self.assertTrue(self.inspect('gpu')['rows'][1]['available'])
        for stamp in (1.0,101.0,True,float('nan'),float('inf'),None,'100'):
            with self.subTest(timestamp=stamp):
                channel['timestamp']=stamp
                row=self.inspect('gpu')['rows'][1]
                self.assertFalse(row['available']);self.assertEqual(row['value'],'—')
        fan=self.data['gpus']['1']['channel_status']['gpu_fan_rpm']
        fan['timestamp']=1.0
        self.assertFalse(self.inspect('gpu')['rows'][-1]['available'])

    def test_rpm_does_not_substitute_percent_or_host_fan_and_zero_is_a_real_reading(self):
        row=self.data['gpus']['1'];row['gpu_fan_rpm']=0
        result=self.inspect('gpu')['rows'][-1]
        self.assertTrue(result['available']);self.assertEqual(result['value'],'0 RPM')
        row['gpu_fan_rpm_scope']='host';row['gpu_fan_percent']=80;self.data['gpu_fan_rpm']=2500
        self.assertFalse(self.inspect('gpu')['rows'][-1]['available'])
        row['gpu_fan_rpm_scope']='card';row['gpu_fan_rpm_timestamp']=96.0
        self.assertFalse(self.inspect('gpu')['rows'][-1]['available'])

    def test_case_and_board_never_borrow_cpu_or_gpu_temperature_and_manual_identity_is_marked(self):
        for component in ('case','board'):
            result=self.inspect(component);rows={row['label']:row for row in result['rows']}
            self.assertEqual(rows['温度']['value'],'—');self.assertEqual(rows['功率']['value'],'—')
        self.assertIn('手动外观',self.inspect('case')['notes'])
        self.assertEqual(self.inspect('case')['rows'][0]['value'],'285 × 462 × 456 mm')
        board={row['label']:row['value'] for row in self.inspect('board')['rows']}
        self.assertEqual(board['主板规格'],'ATX');self.assertEqual(board['尺寸'],'244 × 305 mm')

    def test_memory_uses_whole_pc_totals_and_existing_unit_preferences_are_respected(self):
        result=self.inspect('memory');rows={row['label']:row for row in result['rows']}
        self.assertIn('内存读数为整机合计。',result['notes'])
        self.assertEqual(rows['总内存']['value'],'64.0 GB');self.assertEqual(rows['温度']['value'],'—')
        self.config['top_bar']['items'].insert(0,dict(metric='cpu_usage',prefs=dict(temperature_unit='F',precision=1)))
        rows={row['metric']:row for row in self.inspect('cpu')['rows'] if row.get('metric')}
        self.assertEqual(rows['cpu_temp']['value'],'142.7 °F')

    def test_missing_sample_is_unavailable_without_claiming_hardware_is_unsupported(self):
        result=snapshot({},self.spec,self.config,'not-a-component',now=100.0)
        self.assertEqual(result['component'],'all')
        self.assertEqual(result['state'],'unavailable')
        self.assertNotIn('读数已过期',result['notes'])
        self.assertTrue(all(not row['available'] for row in result['rows']))

    def test_pending_primary_photo_is_visible_in_the_picker_and_board_inspector(self):
        from assembly_parts import choices
        self.config['assembly']['board_model']='gigabyte-z790-aorus-master'
        spec=build_spec(self.data,self.config,dict(state='unavailable'),[])
        result=snapshot(self.data,spec,self.config,'board',now=100.)
        self.assertIn('外观细节尚未核实，当前显示参考布局。',result['notes'])
        self.assertIn('外观待核实',next(row['label'] for row in choices()['boards'] if row['id']=='gigabyte-z790-aorus-master'))

    def test_psu_static_details_do_not_borrow_system_power_or_oled_readings(self):
        for identity,attachment,form in (
                ('asus-tuf-gaming-750b','固定出线','ATX'),
                ('corsair-cx650m-cp9020103','半模组','ATX'),
                ('asus-rog-loki-1000p-sfx-l','全模组','SFX-L'),
                ('asus-rog-thor-1000p2','全模组','ATX')):
            spec=copy.deepcopy(self.spec)
            spec['auxiliary']=dict(psu=dict(model_id=identity))
            result=snapshot(self.data,spec,self.config,'psu',now=100.)
            rows={row['label']:row for row in result['rows']}
            self.assertEqual(len(rows),6)
            self.assertEqual(rows['供电线缆']['value'],attachment)
            self.assertEqual(rows['外形规格']['value'],form)
            self.assertFalse(rows['实际功率']['available'])
            self.assertEqual(rows['实际功率']['value'],'—')
            self.assertTrue(rows['风扇尺寸']['available'])
            if identity=='asus-rog-thor-1000p2':
                self.assertIn('OLED 仅示意外观，尚未绑定功率读数。',result['notes'])
            if identity=='asus-rog-loki-1000p-sfx-l':
                self.assertIn('灯光颜色为外观示意，不代表当前灯效。',result['notes'])


if __name__=='__main__':unittest.main()
