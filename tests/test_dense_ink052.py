"""Generated model-only dense ink: finite exact lookup, never inferred vanes."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine
from hardware_appearance import CATALOG,appearance_for
from hardware_fan_profiles import profile_for

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'native/HardwareDenseInk052.js'


def path_curves(d):
    result=[];current=None
    for command in re.findall(r'[MCQ][^MCQ]*',d):
        v=list(map(float,re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',command[1:])))
        if command[0]=='M':current=v
        else:
            points=[current]+[v[i:i+2]for i in range(0,len(v),2)]
            result.append(points);current=points[-1]
    return result


def bezier(points,t):
    points=[tuple(p)for p in points]
    while len(points)>1:
        points=[tuple(a[k]*(1-t)+b[k]*t for k in range(2))for a,b in zip(points,points[1:])]
    return points[0]


class DenseInk052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QCoreApplication.instance()or QCoreApplication([])
        cls.engine=QJSEngine()
        cls.text=MODULE.read_text(encoding='utf8')
        result=cls.engine.evaluate(re.sub(r'^\.pragma[^\n]*\n','',cls.text))
        if result.isError():raise AssertionError(result.toString())
        cls.info=cls.call('coverage')
        cls.templates=[]
        for line in cls.text.splitlines():
            if line.startswith('    case '):
                key,value=line[9:].split(':return ',1)
                cls.templates.append((json.loads(key),json.loads(value.rstrip(';'))))

    @classmethod
    def tearDownClass(cls):cls.engine.deleteLater();cls.app.processEvents()

    @classmethod
    def call(cls,name,*args):
        result=cls.engine.evaluate('JSON.stringify('+name+'('+','.join(json.dumps(a)for a in args)+'))')
        if result.isError():raise AssertionError(result.toString())
        return json.loads(result.toString())

    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,create=True,side_effect=AssertionError('Pure generated JS and geometry only')))

    def test_table_enumerates_current_real_catalog_without_promoting_whole_card_pending(self):
        self.assertEqual(self.info['catalog_models'],148)
        self.assertEqual(self.info['templates'],len(self.templates))
        self.assertEqual(len(self.templates),27)
        rows={r[0]:r for r in CATALOG if r[1]=='gpu'}
        self.assertEqual(self.info['known_round_axial_models'],len(self.info['covered']))
        self.assertEqual(self.info['known_front_rotors'],sum(len(r['rotors'])for r in self.info['covered']))
        for record in self.info['covered']:
            self.assertIn(record['id'],rows)
            self.assertTrue(record['rotors'])
            a=appearance_for('gpu',rows[record['id']][-1][0]);p=profile_for(a)
            counts=p['blade_counts']or[p['blades']]*a['visible_fan_count']
            for rotor in record['rotors']:
                self.assertEqual(rotor['blades'],counts[rotor['source_index']])
                self.assertGreaterEqual(rotor['blades'],11)
        inno=next(r for r in self.info['covered']if r['id']=='inno3d-ichill-x4-3080')
        self.assertEqual([r['source_index']for r in inno['rotors']],[0,1,2])
        self.assertEqual([r['blades']for r in inno['rotors']],[11,11,11])
        a=appearance_for('gpu',rows[inno['id']][-1][0]);self.assertFalse(profile_for(a)['render_ready'])
        self.assertEqual(profile_for(a)['blade_counts'],[11,11,11,None])

    def test_generated_dependencies_and_runtime_have_no_root_solver_cache_or_frame_work(self):
        for file,expected in self.info['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/file).read_bytes()).hexdigest(),expected,file)
        self.assertLess(MODULE.stat().st_size,26000)
        clean=re.sub(r'//[^\n]*','',self.text)
        for name in ('roots','split','bezier','circlePolynomial','setTimeout','setInterval','fetch','XMLHttpRequest','stats'):
            self.assertNotRegex(clean,r'\b'+name+r'\b')
        self.assertNotRegex(clean,r'(?m)^var\s')
        self.assertFalse(self.info['positions_or_blade_counts_changed'])

    def test_every_template_preserves_the_outer_tip_and_excludes_the_real_cap(self):
        for key,trim in self.templates:
            radius,original=key.split('|',1);radius=float(radius)
            self.assertEqual(self.call('template',radius,original),trim)
            old,new=path_curves(original),path_curves(trim)
            self.assertEqual(len(old),2);self.assertEqual(len(new),2)
            self.assertEqual(old[-1],new[-1])  # Entire actual tip Q is unchanged.
            self.assertAlmostEqual(math.hypot(*new[0][0]),radius+.075+.000001,delta=1.5e-7)
            for curve in new:
                for i in range(65):self.assertGreaterEqual(math.hypot(*bezier(curve,i/64)),radius+.075-1e-7)
            # Independently locate the first source-circle exit, then compare
            # its surviving original curve at many parameter values.
            lo,hi=0.,1.
            for _ in range(60):
                t=(lo+hi)/2
                if math.hypot(*bezier(old[0],t))<radius+.075+.000001:lo=t
                else:hi=t
            start=(lo+hi)/2
            for i in range(33):
                a=bezier(old[0],start+(1-start)*i/32);b=bezier(new[0],i/32)
                self.assertLess(math.dist(a,b),2e-7)

    def test_actual_full_rotor_count_transform_ink_and_cap_radius_survive_lookup(self):
        key,trim=self.templates[0];cap,d=key.split('|',1)
        source='<g transform="scale(-1 1)">'+''.join(
            '<path class="hardware-fan-blade" d="'+d+'" transform="rotate('+str(i*360/11)+')" fill="none" stroke="#dce8ed" stroke-width=".18" data-contour="open-source-leading-edge-and-tip"/>'for i in range(11))
        source+='<circle class="hardware-fan-hub" r="'+cap+'" fill="none" stroke="#dce8ed" stroke-width=".18"/></g>'
        state=dict(kind='gpu',model_mode=True,icon_set='notebook_line')
        p=dict(kind='axial',shape='wide',blades=11)
        output=self.call('apply',source,state,p)
        self.assertNotEqual(source,output)
        a,b=ET.fromstring(source),ET.fromstring(output)
        self.assertEqual(a.attrib,b.attrib);self.assertEqual(len(a),len(b))
        for original,after in zip(a,b):
            for field in ('class','transform','fill','stroke','r'):self.assertEqual(original.get(field),after.get(field))
        self.assertTrue(all(e.get('d')==trim and e.get('stroke-width')=='.15'for e in b if e.tag=='path'))
        self.assertEqual(next(e for e in b if e.tag=='circle').get('stroke-width'),'.16')
        self.assertNotIn('clipPath',output);self.assertNotIn('mask',output);self.assertNotIn('fill="#fff',output)

    def test_unmatched_unknown_small_blower_triangle_and_other_styles_fall_back_exactly(self):
        key,_=self.templates[0];cap,d=key.split('|',1)
        leaf=lambda path:'<path class="hardware-fan-blade" d="'+path+'" fill="none" stroke="#333333" stroke-width=".18"/>'
        circle='<circle class="hardware-fan-hub" r="'+cap+'" fill="none" stroke-width=".18"/>'
        valid='<g>'+leaf(d)*11+circle+'</g>'
        state=dict(kind='gpu',model_mode=True,icon_set='notebook_line');profile=dict(kind='axial',shape='wide',blades=11)
        # Each guard sees an otherwise fully matched eleven-leaf rotor. A
        # broken style/kind gate would now really change this input.
        self.assertNotEqual(self.call('apply',valid,state,profile),valid)
        for style in ('miniature','cartoon','notebook_color','sticker','papercut','sketch','outline'):
            self.assertEqual(self.call('apply',valid,dict(state,icon_set=style),profile),valid)
        for p in (dict(profile,blades=None),dict(profile,kind='blower'),dict(profile,shape='neutral')):
            self.assertEqual(self.call('apply',valid,state,p),valid)
        for override in ({'model_mode':False},{'kind':'cpu'}):
            self.assertEqual(self.call('apply',valid,dict(state,**override),profile),valid)
        seven='<g>'+leaf(d)*7+circle+'</g>'
        self.assertEqual(self.call('apply',seven,state,dict(profile,blades=7)),seven)
        triangle=valid.replace(circle,'<path class="hardware-fan-hub" d="M0 -1L1 1H-1Z" fill="none"/>')
        self.assertEqual(self.call('apply',triangle,state,profile),triangle)
        # One unrecognised path must leave the ENTIRE rotor alone, even after
        # several earlier paths have matched. No half-converted cap or pen.
        unmatched='<g>'+leaf(d)*10+leaf('M1 0C2 0 2 1 2 2Q1 2 0 2')+circle+'</g>'
        self.assertEqual(self.call('apply',unmatched,state,profile),unmatched)
        self.assertIsNone(self.call('template',1.,'Munknown'))

    def test_model_consumer_scope_is_separate_from_topbar_and_clock(self):
        text=(ROOT/'native/HardwareModelDetails.js').read_text(encoding='utf8')
        self.assertIn('if(style==="notebook_line")\n        return DenseInk.apply(Notebook.rotorInk(source,{ink:state.ink}),state,fanProfile)',text)
        self.assertNotIn('DenseInk', (ROOT/'native/HardwareNotebook.js').read_text(encoding='utf8'))
        self.assertNotIn('DenseInk', (ROOT/'native/MetricIcon.qml').read_text(encoding='utf8'))
        self.assertNotIn('DenseInk', (ROOT/'native/HardwareGlyph.qml').read_text(encoding='utf8'))


if __name__=='__main__':unittest.main()
