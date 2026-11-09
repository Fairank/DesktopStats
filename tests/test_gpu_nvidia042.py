"""NVIDIA model contours reference the real retained front, never new fans."""
import json
import math
import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression,qmlContext
from PySide6.QtSvg import QSvgRenderer

from hardware_appearance import CATALOG,appearance_for
from hardware_board_details import drawing_payload
from hardware_fan_profiles import profile_for
from hardware_variants import READY

ROOT=Path(__file__).resolve().parents[1]
NUMBER=r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
NVIDIA={r[0]:r for r in CATALOG if r[1]=='gpu' and r[2]=='nvidia'}


class NvidiaGpuModel042Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen'
        cls.boards=drawing_payload()

    def setUp(self):
        self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native or device API')))
        self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No subprocesses')))
        self.enterContext(patch('socket.socket',side_effect=AssertionError('No network')))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda errors:self.warnings.extend(e.toString() for e in errors))
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQml
import "../native/HardwareModelNvidia042.js" as Model
import "../native/HardwareSolid.js" as Solid
import "../native/HardwareBoardDesigns.js" as Board
QtObject {
 function rows(){return JSON.stringify(Model.records())}
 function initialized(){return JSON.stringify(Model.rows!==null)}
 function row(state){return JSON.stringify(Model.profile(state))}
 function source(state){var g=Solid.geometry(state);var c=Board.colors(state,Solid.palette(state));
     var variant=Board.variantFace(state,g,c);
     return JSON.stringify({g:g,front:variant||Solid.front(state,g,c),variant:!!variant})}
}''',QUrl.fromLocalFile(str(ROOT/'tests/NvidiaGpuModel042Fixture.qml')))
        self.object=self.component.create()
        self.assertIsNotNone(self.object,[e.toString() for e in self.component.errors()])

    @property
    def rows(self):
        return self.call('rows')

    def tearDown(self):
        self.object.deleteLater();self.component.deleteLater();self.engine.deleteLater()
        self.app.processEvents();self.assertEqual(self.warnings,[])

    def call(self,name,*args):
        expression=QQmlExpression(qmlContext(self.object),self.object,name+'('+','.join(json.dumps(a) for a in args)+')')
        result=expression.evaluate()
        self.assertFalse(expression.hasError(),expression.error().toString())
        return json.loads(result[0] if isinstance(result,tuple) else result)

    @staticmethod
    def appearance(id):
        source=NVIDIA[id];a=appearance_for('gpu',source[-1][0])
        return {**a,'design_id':id,'model_id':id,'fan_count':a['visible_fan_count'],'icon_set':'miniature','ink':'#40505e'}

    def test_exact_ninety_three_skus_and_safe_profile_lookup(self):
        self.assertEqual(len(self.rows),93);self.assertEqual(set(self.rows),set(NVIDIA))
        self.assertIn('gigabyte-fx5200-n52128d-rev10-reference',self.rows)
        for id in NVIDIA:
            self.assertEqual(self.call('row',self.appearance(id)),self.rows[id])
        valid=self.appearance(next(iter(NVIDIA)))
        invalid=({},None,{'kind':'gpu','model_id':'__proto__'},{'kind':'gpu','model_id':'constructor'},
                 {**valid,'model_id':'missing'},{**valid,'model_id':0},{**valid,'model_id':'x'*97},
                 {**valid,'kind':'cpu'},{**valid,'series_id':'nvidia_founders'})
        for state in invalid:
            self.assertIsNone(self.call('row',state))

    def test_cold_catalog_stays_unallocated_for_topbar_cpu_or_invalid_gpu_identity(self):
        self.assertFalse(self.call('initialized'))
        valid=self.appearance(next(iter(NVIDIA)))
        for state in ({},None,{'kind':'cpu','model_id':valid['model_id'],'series_id':valid['series_id']},
                      {**valid,'kind':'memory'},{**valid,'model_id':'__proto__'},
                      {**valid,'model_id':'constructor'},{**valid,'model_id':'not-in-the-catalog'},
                      {**valid,'model_id':'x'*97},{**valid,'model_id':False},
                      {**valid,'series_id':None},{**valid,'series_id':34}):
            self.assertIsNone(self.call('row',state))
            self.assertFalse(self.call('initialized'))
        self.assertEqual(self.call('row',valid)['profile_ref'],valid['model_id'])
        self.assertTrue(self.call('initialized'))
        self.assertEqual(len(self.rows),93)
        self.assertIn('gigabyte-fx5200-n52128d-rev10-reference',self.rows)

    def test_every_trace_is_an_existing_original_front_facet_not_io_or_rotor(self):
        numbers=lambda d:list(map(float,re.findall(NUMBER,d)))
        shapes=('path','rect','line','polygon','polyline','ellipse','circle')
        signatures=set()
        for id,row in self.rows.items():
            with self.subTest(id=id):
                state=self.appearance(id);original=self.call('source',state)
                self.assertEqual(row['profile_ref'],id)
                self.assertEqual(row['series_id'],state['series_id'])
                self.assertEqual(row['recipe'],self.boards[id]['recipe'])
                if id in ('msi-n480gtx-m2d15','gigabyte-gtx460-oc-1g-rev1'):
                    # These observed faces own their native semantic bank/body;
                    # repeating old generic contours would draw a second grid.
                    self.assertIs(row.get('inline_observed_face'),True)
                    self.assertEqual(row['traces'],[])
                    self.assertTrue(original['variant'])
                else:
                    self.assertGreaterEqual(len(row['traces']),2)
                    self.assertNotIn('inline_observed_face',row)
                self.assertLessEqual(len(row['traces']),6)
                nodes=[n for n in ET.fromstring('<g>'+original['front']+'</g>').iter() if n.tag in shapes]
                prefix=('HardwareBoardDesigns.variantFace:'+row['recipe'] if original['variant'] else 'HardwareSeriesShapes.face:'+row['series_id'])
                seen=set()
                for trace in row['traces']:
                    self.assertIn(trace['role'],('edge','vent','trim','material'))
                    self.assertGreaterEqual(trace['width'],.08);self.assertLessEqual(trace['width'],.14)
                    self.assertTrue(trace['source_field'].startswith(prefix+':shape['))
                    index=int(re.search(r'shape\[(\d+)\]$',trace['source_field'])[1])
                    self.assertNotIn(index,seen);seen.add(index)
                    node=nodes[index];self.assertIn(node.tag,('path','rect','line','polygon','polyline'))
                    self.assertNotIn('fan',node.get('class',''))
                    self.assertNotIn('rotor',node.get('class',''))
                    self.assertRegex(trace['d'],r'^M')
                    self.assertFalse(re.search('[a-zAa]',trace['d']))
                    self.assertTrue(all(math.isfinite(v) and -10<=v<=110 for v in numbers(trace['d'])))
                    # Current front studies all normalize exactly to panel space.
                    # Keeping this explicit prevents silently dropping rotations.
                    self.assertNotIn('m',trace)
                    if node.tag=='path':
                        self.assertEqual(re.findall('[A-Za-z]',trace['d']),re.findall('[A-Za-z]',node.get('d')))
                        self.assertEqual(len(numbers(trace['d'])),len(numbers(node.get('d'))))
                        for actual,expected in zip(numbers(trace['d']),numbers(node.get('d'))):
                            self.assertAlmostEqual(actual,expected,delta=.0000051)
                    elif node.tag=='rect':
                        x,y,w,h=(float(node.get(k,0)) for k in ('x','y','width','height'))
                        # Native rect -> explicit boundary with same rounded rail.
                        # This is a material contour, never replacement silhouette.
                        self.assertIn(round(x,5),[round(n,5) for n in numbers(trace['d'])])
                        self.assertIn(round(y,5),[round(n,5) for n in numbers(trace['d'])])
                        self.assertIn(round(x+w,5),[round(n,5) for n in numbers(trace['d'])])
                        self.assertIn(round(y+h,5),[round(n,5) for n in numbers(trace['d'])])
                source='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'+''.join('<path d="'+t['d']+'" fill="none" stroke="#40505e"/>' for t in row['traces'])+'</svg>'
                self.assertTrue(QSvgRenderer(source.encode()).isValid())
                self.assertLessEqual(len(source.encode()),4096)
                signatures.add(tuple(t['d'] for t in row['traces']))
        self.assertGreaterEqual(len(signatures),65)

    def test_fan_reference_keeps_physical_and_front_counts_independent(self):
        for id,row in self.rows.items():
            with self.subTest(id=id):
                a=appearance_for('gpu',NVIDIA[id][-1][0]);fan=profile_for(a)
                self.assertEqual(row['fan_ref']['physical_count'],a['fan_count'])
                self.assertEqual(row['fan_ref']['front_count'],a['visible_fan_count'])
                self.assertEqual(row['fan_ref']['series_id'],a['series_id'])
                expected='not_applicable' if a['visible_fan_count']==0 else 'reviewed' if fan.get('render_ready') else 'pending'
                self.assertEqual(row['fan_ref']['profile_status'],expected)
                if expected=='pending':self.assertIn('blade_geometry_not_reviewed',row['unknown'])
        for id,physical,front in [('asus-astral-5080-oc',4,3),('inno3d-ichill-x4-3080',4,3),('galax-hof-5080-extreme',4,3),('msi-expert-4080super',2,1),('galax-sg-plus-4070tis',None,3),('gigabyte-gt1030-silent-lp-2g',0,0)]:
            self.assertEqual((self.rows[id]['fan_ref']['physical_count'],self.rows[id]['fan_ref']['front_count']),(physical,front))

    def test_sources_unknowns_and_shared_exteriors_are_honest(self):
        for id,row in self.rows.items():
            self.assertIn(NVIDIA[id][8],row['sources'])
            self.assertEqual(len(row['sources']),len(set(row['sources'])))
            self.assertTrue(all(s.startswith('https://') for s in row['sources']))
            self.assertIn('contour_spacing_is_illustrative_not_cad',row['unknown'])
            self.assertIn('hidden_pcb_layout_not_drawn',row['unknown'])
            if self.boards[id]['power_position']=='unknown':self.assertIn('power_connector_position_unknown',row['unknown'])
            variant=READY.get(id,{})
            if variant.get('visual_relation')=='shared':
                base=variant['base_model_id'];self.assertIn('shared_exterior_with:'+base,row['unknown'])
                # An OC label is not permission to manufacture another shell.
                self.assertEqual([t['d'] for t in row['traces']],[t['d'] for t in self.rows[base]['traces']])


if __name__=='__main__':
    unittest.main()
