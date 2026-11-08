"""Real reference wiring, stable fixed ports and unchanged strict router."""
import ast
import copy
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QGuiApplication,QOpenGLContext
from PySide6.QtQml import QQmlEngine

import hardware_packs
import assembly_auxiliary as auxiliary
import assembly_cooling as cooling
from cooling_catalog import _FAN_BY_ID
from assembly_parts import reference_preset,fit_messages
from assembly_profiles import bake_profiles
from assembly_scene_cache import SceneCache
from assembly_spec import build_spec
from stats_config import DEFAULT

ROUTER_AST_SHA='ee90555f30df246286921c5d625c610ebf54a57c4ea8c2d304779d554cbcd323'
# Pre-change actual three-reference ports, rounded to6 decimals for the
# serialized boundary. Only an unverified rear flexible source is excluded;
# its fixed target, and every other socket/normal-derived plug end, remain.
FIXED_PORTS_SHA={
    'air':'316ecef774c8cf2cffeb2d3bddfe33aa442bdb655e727afa5d0e2302d7c45af4',
    'aio':'b9dd2aeed32c6ab5c46d5caba4e90f6e82d7235aade3a20f00f33329907ce600',
    'loop':'675f2a7e677521ffbc5c1ca25e65583aed5f9ffe030805d3a786efa5c1bae27f'}
# The legacy isolated_fan API was byte-compared before production changes;
# these samples include its flexible lead and connector, not just its body.
DEFAULT_FAN_SHA={
    ('eco','front'):'e5e75643269335a8e9cfd24c45d0d0e7859430e80910904ea1cdb9927c5d8a0b',
    ('eco','rear'):'2eecdeda697d875a2a75bde7c4d5ccd45da7d6852722dc4ea62ed6f26d78028a',
    ('balanced','front'):'323c102b6f3e4ceca37cac93061126cd6fc95fdbaffe6ea7764d41c669f5548e',
    ('balanced','rear'):'332a7e31b8a931855febabb29f80e4342c9223b2ad5e85deea6c6dc8f0a0687f',
    ('close','front'):'6b0d6533321868596ce1a4f4a3a235d41f63ead78026ffb0786c36f4e40aaa95',
    ('close','rear'):'011ca48334fad22aa5eb7d7f9c629b2e8290ceb6fc1b8850c6413b8dabd32af8'}


def normalized(value):
    if isinstance(value,float):return round(value,6)
    if isinstance(value,(tuple,list)):return [normalized(item) for item in value]
    return value


def port_digest(cables):
    rows=[]
    for cable in cables:
        row=[cable['kind'],cable['source_owner'],cable['target_owner'],normalized(cable['target_socket']),normalized(cable['end'])]
        if not str(cable['source_owner']).startswith('fans:rear:'):
            row.extend((normalized(cable['source_socket']),normalized(cable['start'])))
        rows.append(row)
    return hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()


def mesh_digest(meshes):
    value=hashlib.sha256()
    for mesh in meshes:
        value.update((mesh.name+'|'+mesh.component+'|'+mesh.part_id).encode())
        value.update(struct.pack('<'+str(len(mesh.vertices))+'d',*mesh.vertices))
        value.update(struct.pack('<10d',*mesh.position,*mesh.axis,*mesh.color))
        value.update(struct.pack('<?i',mesh.rotor,mesh.direction))
    return value.hexdigest()


def projected(point,yaw):
    y,p=math.radians(yaw),math.radians(-8)
    return (point[0]*math.cos(y)-point[2]*math.sin(y),
            -point[0]*math.sin(y)*math.sin(p)+point[1]*math.cos(p)-point[2]*math.cos(y)*math.sin(p))


class CaseFanCableRouting048Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Software/private fixtures only')

    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(target,side_effect=AssertionError('No native, device, process or worker'),create=True))
        directory=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(hardware_packs,'_store',hardware_packs.PackStore(directory/'packs')))

    def tearDown(self):
        self.assertEqual(self.app.topLevelWindows(),[])
        self.assertIsNone(QOpenGLContext.currentContext())

    def test_route_solver_and_padding_contract_have_no_algorithm_change(self):
        node=ast.parse(inspect.getsource(auxiliary.route_cable)).body[0]
        self.assertEqual(hashlib.sha256(ast.dump(node).encode()).hexdigest(),ROUTER_AST_SHA)

    def test_isolated_default_fans_keep_bytes_and_tail_override_never_moves_the_body(self):
        model=_FAN_BY_ID['arctic-p12-pwm']
        for level in ('eco','balanced','close'):
            for mount in ('front','rear'):
                default=cooling._Builder(level);flipped=cooling._Builder(level)
                kwargs=dict(part='fans:'+mount+':0')
                cooling._fan(default,model,(0.,0.,0.),(0.,0.,1.),(1.,0.,0.),**kwargs)
                cooling._fan(flipped,model,(0.,0.,0.),(0.,0.,1.),(1.,0.,0.),wire_sign_override=1 if mount=='rear' else -1,**kwargs)
                actual,other=default.finish(),flipped.finish()
                self.assertEqual(mesh_digest(actual),DEFAULT_FAN_SHA[level,mount])
                body=lambda meshes:tuple(mesh for mesh in meshes if not mesh.name.endswith(('-power-lead','-power-connector')))
                self.assertEqual(body(actual),body(other))
                self.assertEqual(default.fans,flipped.fans)
                self.assertTrue(all(row['position_verified'] is False for row in default.wire_anchors))

    def test_three_real_references_keep_all_known_routes_fixed_ports_and_clear_actual_segments(self):
        engine=QQmlEngine();warnings=[]
        engine.warnings.connect(lambda values:warnings.extend(value.toString() for value in values))
        try:
            for kind in ('air','aio','loop'):
                with self.subTest(kind=kind):
                    config=copy.deepcopy(DEFAULT);config['assembly']=reference_preset({},kind)
                    spec=bake_profiles(build_spec({},config,{},[]),engine)
                    cache=SceneCache();calls=[];original=auxiliary.route_cable
                    def observe(*args,**kwargs):
                        path,state=original(*args,**kwargs)
                        calls.append((path,state,args[4] if len(args)>4 else kwargs.get('obstacles',())))
                        return path,state
                    try:
                        with patch.object(auxiliary,'route_cable',new=observe):scene=cache.build(spec)
                        meta=scene.metadata;cables=meta['auxiliary']['cables'];anchors=meta['attachment_anchors']
                        self.assertEqual(meta['cooling']['rejected'],[])
                        self.assertEqual(meta['auxiliary']['rejected'],[])
                        self.assertEqual(meta['auxiliary']['omitted_routes'],[])
                        self.assertEqual(len(cables),14 if kind=='air' else 8)
                        self.assertEqual(port_digest(cables),FIXED_PORTS_SHA[kind])
                        self.assertFalse(any(cable['external_route'] for cable in cables))
                        self.assertEqual(fit_messages(spec,meta),[])
                        fans=[row for row in cables if str(row['source_owner']).startswith('fans:')]
                        self.assertEqual(len(fans),4)
                        fan_ends=[row for row in meta['cooling']['wire_anchors'] if row.get('role')=='case']
                        for end in fan_ends:
                            self.assertFalse(end['position_verified'])
                            self.assertTrue(all(abs(end['position'][axis])<=scene.dimensions[axis]/2 for axis in range(3)))
                        for cable in fans:
                            self.assertFalse(cable['routing_failed'])
                            actual=next((row for row in calls if row[0]==cable['path']),None)
                            self.assertIsNotNone(actual)
                            # Replay the original exact route obstacles. Final
                            # shifted strand clearance also ran in the producer.
                            path,state,obstacles=actual
                            for a,b in zip(path,path[1:]):
                                self.assertFalse(any(auxiliary.segment_hits_box(a,b,bounds,1.1) for bounds in obstacles))
                        if kind=='aio':
                            self.assertTrue(all(c['preferred_waypoints_used'] for c in fans))
                            # Check actual final path pieces, not the preference
                            # flag: no long Y/Z diagonal through the front chamber.
                            board_x=anchors['board']['position'][0]
                            for cable in fans:
                                diagonals=[(a,b) for a,b in zip(cable['path'],cable['path'][1:])
                                    if abs(a[1]-b[1])>30 and abs(a[2]-b[2])>30 and (a[0]+b[0])/2<board_x-4]
                                for yaw in (-70,-110):
                                    projected_length=sum(math.dist(projected(a,yaw),projected(b,yaw)) for a,b in diagonals)
                                    self.assertAlmostEqual(projected_length,0.,msg=(cable['source_owner'],yaw,diagonals))
                        calls.clear()
                    finally:cache.clear()
        finally:
            engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(warnings,[])

    def test_real_remaining_external_route_is_visible_in_fit_messages(self):
        # A deliberately out-of-case fixed header may not be moved inward by
        # this change. The real producer must retain its external warning.
        spec=dict(auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=True))
        anchors=dict(case_dimensions=(300.,500.,500.),case=dict(layout='tower',features=[]),
            connectors=dict(atx24=[dict(position=(-180.,150.,20.),normal=(-1.,0.,0.),along=(0.,1.,0.))]))
        meshes,metadata=auxiliary.add_auxiliary(spec,anchors,'eco')
        self.assertTrue(meshes);self.assertEqual(len(metadata['cables']),1)
        self.assertTrue(metadata['cables'][0]['external_route'])
        self.assertIn('cable_reference_route_exceeds_case',metadata['warnings'])
        message='部分参考线缆超出机箱范围，请检查走线。'
        self.assertIn(message,fit_messages(spec,{'auxiliary':metadata}))
        self.assertNotIn(message,fit_messages({},dict(auxiliary=dict(warnings=[]))))

    def test_missing_or_malformed_wire_records_do_not_become_case_fan_sources(self):
        spec=dict(auxiliary=dict(cables_enabled=True))
        for records in (None,[None,7,{},dict(role='case',owner=[])],[]):
            anchors=dict(case_dimensions=(300.,500.,500.),case={},cooling=dict(wire_anchors=records))
            _meshes,metadata=auxiliary.add_auxiliary(spec,anchors,'eco')
            self.assertEqual(metadata['cables'],[])
        # A valid legacyendpoint with a malformedowner must not be hashed as
        # acasefanID. Keep the old safe routing behavior for such referenceinput.
        anchors=dict(case_dimensions=(300.,500.,500.),case={},
            board=dict(position=(90.,0.,0.),normal=(-1.,0.,0.),up=(0.,1.,0.)),
            connectors=dict(fan=[dict(position=(80.,30.,0.),normal=(-1.,0.,0.))]),
            cooling=dict(wire_anchors=[dict(position=(0.,150.,0.),normal=(1.,0.,0.),
                kind='fan4',owner=[],role='case',connector_rendered=True)]))
        _meshes,metadata=auxiliary.add_auxiliary(spec,anchors,'eco')
        self.assertEqual(len(metadata['cables']),1)


if __name__=='__main__':unittest.main()
