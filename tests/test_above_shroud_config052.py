"""Exact above-shroud fan preferences and real picker JavaScript, no scene IO."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine

from assembly_config import COOLER_MOUNTS,FAN_MOUNTS,validate_assembly
from assembly_parts import choices,fit_messages,selected_parts
import hardware_packs
from hardware_packs import PackStore
from top_bar_config import HARDWARE_ICON_STYLES

CASE='lian-li-lancool-iii'
MOUNT='above_psu_shroud'
LEGACY=('front','top','rear','bottom','side')
QML=Path(__file__).resolve().parents[1]/'native'/'AssemblyParts.qml'


def _function(source,name):
    """Read the production QML function verbatim, including nested literals."""
    start=source.index('function '+name+'(')
    opening=source.index('{',start)
    depth=0;quote='';escaped=False
    for index in range(opening,len(source)):
        char=source[index]
        if quote:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char==quote:quote=''
            continue
        if char in ('"',"'"):quote=char
        elif char=='{':depth+=1
        elif char=='}':
            depth-=1
            if depth==0:return source[start:index+1]
    raise AssertionError('Unclosed production QML function '+name)


class AboveShroudConfig052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,create=True,side_effect=AssertionError('Pure configuration/JavaScript only')))
        folder=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(hardware_packs,'_store',PackStore(folder/'packs')))

    def test_six_fan_mounts_and_five_cooler_mounts_preserve_legacy_values(self):
        self.assertEqual(COOLER_MOUNTS,LEGACY)
        self.assertEqual(FAN_MOUNTS,(*LEGACY,MOUNT))
        rows=[dict(model='arctic-p12-pwm',mount=mount,count=1,direction='intake') for mount in FAN_MOUNTS]
        clean=validate_assembly(dict(case_fans=rows))
        self.assertEqual(clean['case_fans'],rows)
        self.assertIsNot(clean['case_fans'],rows)
        for mount in LEGACY:
            self.assertEqual(validate_assembly(dict(cooler_mount=mount))['cooler_mount'],mount)
        for value in (dict(cooler_mount=MOUNT),dict(case_fans=rows+[rows[-1]]),
                      dict(case_fans=[rows[-1],rows[-1]]),
                      dict(case_fans=[dict(rows[-1],mount='above-psu-shroud')]),
                      dict(case_fans=[dict(rows[-1],mount='../above_psu_shroud')])):
            with self.subTest(value=value),self.assertRaises(ValueError):validate_assembly(value)

    def test_original_mount_token_and_safe_part_styles_roundtrip_without_regex_expansion(self):
        row=dict(model='arctic-p12-pwm',mount=MOUNT,count=3,direction='intake')
        for style in HARDWARE_ICON_STYLES:
            original=dict(case_model=CASE,case_fans=[row],part_styles={'fans:above-psu-shroud:1':style})
            before=copy.deepcopy(original);clean=validate_assembly(original)
            self.assertEqual(selected_parts(clean)['cooling']['case_fans'],[row])
            self.assertEqual(clean['part_styles'],original['part_styles'])
            self.assertEqual(original,before)
        for target in ('fans:above_psu_shroud:1','fans:../above:1','fans:above/psu:1',
                       'fans:above-psu-shroud:1:extra:too-many','fans:'+('x'*65)):
            with self.subTest(target=target),self.assertRaises(ValueError):
                validate_assembly(dict(part_styles={target:'cartoon'}))

    def test_choice_lists_are_distinct_detached_and_legacy_radiator_alias_stays_five(self):
        result=choices(lambda text:'T:'+text)
        self.assertEqual([r['id'] for r in result['mounts']],list(LEGACY))
        self.assertEqual(result['radiator_mounts'],result['mounts'])
        self.assertEqual([r['id'] for r in result['fan_mounts']],list(FAN_MOUNTS))
        self.assertEqual(result['fan_mounts'][-1],dict(id=MOUNT,label='T:电源罩上方'))
        result['fan_mounts'][0]['label']='changed'
        self.assertEqual(result['mounts'][0]['label'],'T:前部')
        result['radiator_mounts'][0]['label']='also changed'
        self.assertEqual(result['mounts'][0]['label'],'T:前部')
        self.assertEqual(choices()['fan_mounts'][0]['label'],'前部')

    def test_actual_controller_edit_preserves_other_mounts_and_validates_complete_group(self):
        from assembly_tools import AssemblyTools
        previous=validate_assembly(dict(case_fans=[dict(model='arctic-p12-pwm',mount='rear',count=1,direction='exhaust')]))
        node=SimpleNamespace(_draft={'assembly':previous});edits=[]
        def edit(value,**kwargs):
            value['assembly']=validate_assembly(value['assembly'])
            edits.append((value,kwargs));node._draft=value
        node.edit=edit
        AssemblyTools.changeAssemblyFan(node,MOUNT,'arctic-p12-pwm',3,'intake')
        self.assertEqual(node._draft['assembly']['case_fans'],previous['case_fans']+[
            dict(model='arctic-p12-pwm',mount=MOUNT,count=3,direction='intake')])
        self.assertEqual(edits[-1][1]['merge_key'],('assembly','fan',MOUNT))
        AssemblyTools.changeAssemblyFan(node,MOUNT,'',1,'intake')
        self.assertEqual(node._draft['assembly']['case_fans'],previous['case_fans'])
        count=len(edits);AssemblyTools.changeAssemblyFan(node,'../bad','arctic-p12-pwm',1,'intake')
        self.assertEqual(len(edits),count)

    def test_missing_special_plane_has_a_specific_user_message(self):
        message=fit_messages({},dict(cooling=dict(rejected=[dict(kind='case_fan',
            mount=MOUNT,reason='case_fan_mount_reference_unavailable')])))
        self.assertEqual(message,['此安装位的参考安装面尚未确认，整组风扇未放入。'])

    def javascript(self,root,expression):
        source=QML.read_text(encoding='utf-8')
        functions='\n'.join(_function(source,name) for name in ('fan','visibleFanMounts','fansFor','countsFor'))
        script='(function(){const root='+json.dumps(root)+';const caseInfo=root.caseInfo;const config=root.config;'+functions+\
            ';root.fan=fan;return '+expression+';})()'
        engine=QJSEngine();value=engine.evaluate(script,'AssemblyParts-production-functions.js')
        self.assertFalse(value.isError(),value.toString())
        return value.toVariant()

    def picker(self,case_id,selected=()):
        return dict(caseInfo=dict(case_id=case_id,fan_mounts=[dict(position='front',size_mm=[120],count=3),
            *([dict(position=MOUNT,size_mm=[120],count=3)] if case_id==CASE else [])]),
            config=dict(case_fans=list(selected)),counts=[dict(id=str(i),label=str(i)) for i in range(1,5)],
            catalog=dict(mounts=[dict(id=m,label=m) for m in LEGACY],
                fan_mounts=[dict(id=m,label=m) for m in FAN_MOUNTS],
                radiator_mounts=[dict(id=m,label=m) for m in LEGACY],
                fans=[dict(id='',label='none'),dict(id='p12',size_mm=120),dict(id='p14',size_mm=140)]))

    def test_real_qml_mount_filter_is_exact_case_only_and_keeps_stale_selection(self):
        self.assertEqual([r['id'] for r in self.javascript(self.picker(CASE),'visibleFanMounts()')],list(FAN_MOUNTS))
        for case_id in ('lian-li-lancool-207','nzxt-h5-flow-2024','', 'other-case'):
            root=self.picker(case_id)
            self.assertEqual([r['id'] for r in self.javascript(root,'visibleFanMounts()')],list(LEGACY))
            root['config']['case_fans']=[dict(model='p14',mount=MOUNT,count=4,direction='exhaust')]
            self.assertEqual([r['id'] for r in self.javascript(root,'visibleFanMounts()')],list(FAN_MOUNTS))
            self.assertEqual([r['id'] for r in self.javascript(root,'fansFor("above_psu_shroud")')],['','p14'])
            self.assertEqual([r['id'] for r in self.javascript(root,'countsFor("above_psu_shroud","p14")')],['4'])

    def test_real_qml_capacity_filter_and_legacy_catalog_fallback_do_not_open_radiators(self):
        root=self.picker(CASE)
        self.assertEqual([r['id'] for r in self.javascript(root,'fansFor("above_psu_shroud")')],['','p12'])
        self.assertEqual([r['id'] for r in self.javascript(root,'countsFor("above_psu_shroud","p12")')],['1','2','3'])
        del root['catalog']['fan_mounts']
        self.assertEqual([r['id'] for r in self.javascript(root,'visibleFanMounts()')],list(LEGACY))
        source=QML.read_text(encoding='utf-8')
        self.assertIn('model:root.catalog.radiator_mounts || root.catalog.mounts || []',source)
        self.assertIn('model:root.visibleFanMounts()',source)
        self.assertNotIn(MOUNT,{r['id'] for r in choices()['radiator_mounts']})


if __name__=='__main__':unittest.main()
