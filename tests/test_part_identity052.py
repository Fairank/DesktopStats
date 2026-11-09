"""Authored IDs retain individual inspection identity without new sampling."""
import unittest
from assembly_inspection import part_family,snapshot


class PartIdentityTests(unittest.TestCase):
    def test_independent_fan_family_comes_from_exact_authored_metadata(self):
        details={'cooling':{'parts':[
            dict(id='case-fan:0',kind='case_fan',label='Rear reference fan'),
            dict(id='radiator-fan:0',kind='radiator_fan',label='Radiator fan')]}}
        self.assertEqual(part_family('case-fan:0',details),'fans')
        self.assertEqual(part_family('radiator-fan:0',details),'cooler')
        self.assertEqual(part_family('case-fan:missing',details),'all')
        self.assertEqual(part_family('case-fan:0',{}),'all')
        details['hardware']={'parts':[dict(id='case-fan:0',component='gpu')]}
        self.assertEqual(part_family('case-fan:0',details),'all')
        details={'cooling':{'parts':[dict(id='odd:0',kind={},component=[])]}}
        self.assertEqual(part_family('odd:0',details),'all')

    def test_actual_case_fan_inspection_preserves_label_and_does_not_borrow_cpu_rpm(self):
        details={'cooling':{'parts':[dict(id='case-fan:0',kind='case_fan',
                    model_id='arctic-p12-pwm',label='Rear P12',size_mm=120.,depth_mm=25.,mount='rear')]}}
        data=dict(time=100.,cpu_temp=82.,cpu_fan_rpm=1600.)
        result=snapshot(data,{}, {},'case-fan:0',now=100.,scene_metadata=details)
        self.assertEqual(result['component'],'case-fan:0')
        self.assertEqual(result['identity'],'Rear P12')
        rpm=[row for row in result['rows'] if row['label']=='实测转速']
        self.assertEqual(len(rpm),1);self.assertFalse(rpm[0]['available'])
        self.assertEqual(rpm[0]['value'],'—')
        self.assertNotIn('cpu_temp',{row.get('metric') for row in result['rows']})

    def test_exact_fan_style_keys_roundtrip_and_paint_only_the_selected_physical_part(self):
        from assembly_config import validate_assembly
        from assembly_geometry import Mesh,box
        from assembly_style import apply_model_styles
        from dataclasses import replace
        styles={'case-fan:0':'notebook_line','radiator-fan:0':'cartoon'}
        self.assertEqual(validate_assembly({'part_styles':styles})['part_styles'],styles)
        a=Mesh('fan-a',box(8,8,2),(.2,.4,.5,1.),component='fans',part_id='case-fan:0')
        b=replace(a,name='fan-b',part_id='case-fan:1')
        c=replace(a,name='rad-fan',component='cooler',part_id='radiator-fan:0')
        painted,meta=apply_model_styles((a,b,c),'miniature',styles,(100,100,100),{})
        self.assertEqual(meta['mesh_style_ids'],('notebook_line','miniature','cartoon'))
        for source,value in zip((a,b,c),painted):
            self.assertIs(value.vertices,source.vertices)
            self.assertEqual((value.position,value.part_id,value.component),(source.position,source.part_id,source.component))
        for bad in ('case-fan:../../0','case-fan:','radiator-fan:0/1','other:0'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_assembly({'part_styles':{bad:'cartoon'}})

    def test_case_cover_and_window_preserve_identity_without_borrowing_case_dimensions_or_power(self):
        case=dict(label='ROG Strix Helios GX601',dimensions_verified=True,
                  dimensions_mm=dict(width=250,height=591,depth=565))
        parts=[dict(id='case:psu-rear-cover',kind='case_cover',component='case',
                    label='GX601 后段电源罩',assembly_state='installed'),
               dict(id='case:psu-side-window',kind='case_window',component='case',
                    label='GX601 透明观察窗',assembly_state='installed')]
        details=dict(hardware=dict(parts=parts),case_shroud=dict(removed_parts=[
            dict(id='case:psu-front-cover',reason='front_cover_removed_for_radiator_lower_bay')]))
        data=dict(time=100.,cpu_temp=82.,cpu_power=170.,gpu_power=350.)
        for part in parts:
            with self.subTest(target=part['id']):
                result=snapshot(data,dict(case=case),{},part['id'],now=100.,scene_metadata=details)
                self.assertEqual(result['component'],part['id'])
                self.assertEqual(result['identity'],part['label'])
                rows={row['label']:row for row in result['rows']}
                self.assertEqual(rows['所属机箱']['value'],case['label'])
                self.assertEqual(rows['装配状态']['value'],'已安装（参考装配）')
                self.assertFalse(rows['制造尺寸']['available'])
                self.assertFalse(rows['实测功率']['available'])
                self.assertEqual(rows['实测功率']['value'],'—')
                self.assertFalse(any('metric' in row for row in result['rows']))
                self.assertNotIn('250',str(result['rows']))
                if part['kind']=='case_window':self.assertTrue(any('不是电子显示屏' in note for note in result['notes']))
        whole=snapshot(data,dict(case=case),{},'case',now=100.,scene_metadata=details)
        self.assertEqual(whole['identity'],case['label'])
        self.assertTrue(any('已移除前段电源罩' in note for note in whole['notes']))


import test_part_motion_ui052 as ui


class PartIdentityUiTests(unittest.TestCase):
    setUpClass=classmethod(ui.PartMotionUiTests.setUpClass.__func__)
    setUp=ui.PartMotionUiTests.setUp
    tearDown=ui.PartMotionUiTests.tearDown

    def test_actual_inspector_preserves_nonprefix_fan_selection_and_static_details(self):
        metadata=self.window.viewport.scene.metadata
        metadata['cooling']['parts'].append(dict(id='case-fan:0',kind='case_fan',
            model_id='arctic-p12-pwm',label='Rear P12',mount='rear',size_mm=120.,depth_mm=25.))
        self.window._refresh_part_choices()
        self.window.component_choice.setCurrentIndex(self.window.component_choice.findData('case-fan:0'))
        self.app.processEvents()
        self.assertEqual(self.window.selected_component,'case-fan:0')
        self.assertEqual(self.window.viewport.selected,'case-fan:0')
        self.assertEqual(self.window.inspection_state['component'],'case-fan:0')
        self.assertEqual(self.window.inspection_state['identity'],'Rear P12')
        self.assertTrue(self.window.gpu_remove.isHidden())

    def test_independent_case_cover_can_be_selected_styled_and_temporarily_hidden(self):
        metadata=self.window.viewport.scene.metadata
        part=dict(id='case:psu-rear-cover',kind='case_cover',component='case',
                  label='GX601 后段电源罩',assembly_state='installed')
        metadata['hardware']['parts'].append(part)
        self.window._refresh_part_choices()
        self.window.component_choice.setCurrentIndex(self.window.component_choice.findData(part['id']))
        self.app.processEvents()
        self.assertEqual(self.window.selected_component,part['id'])
        self.assertEqual(self.window.viewport.selected,part['id'])
        self.assertEqual(self.window.inspection_state['identity'],part['label'])
        calls=[];self.controller.changeAssemblyPartStyle=lambda target,style:calls.append((target,style))
        for style in ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut'):
            choice=self.window.part_style_choice
            index=choice.findData(style);self.assertGreaterEqual(index,0)
            choice.setCurrentIndex(index);choice.activated.emit(index)
            self.assertEqual(calls[-1],(part['id'],style))
        self.assertTrue(self.window.part_hidden.isEnabled())
        self.window.part_hidden.setChecked(True);self.app.processEvents()
        self.assertEqual(self.window.viewport.hidden_calls[-1],(part['id'],True))
        self.assertIn(part['id'],self.window.viewport.hidden_parts)
        self.assertTrue(self.window._restore_hidden())
        self.assertEqual(self.window.viewport.hidden_parts,set())
        self.assertEqual(self.window.selected_component,part['id'])


if __name__=='__main__':unittest.main()
