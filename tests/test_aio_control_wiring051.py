"""Documented LFIII control topology, source-qualified CPU_FAN and real routes."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QGuiApplication,QOpenGLContext
from PySide6.QtQml import QQmlEngine
import hardware_packs
from hardware_packs import PackStore
from assembly_auxiliary import add_auxiliary,_segment_triangle,_aio_tube_obstacles,segment_hits_box
from assembly_cooling import add_cooling,_Builder,_lfiii_control_reference
from assembly_geometry import build_scene
from assembly_parts import reference_preset,fit_messages
from assembly_profiles import bake_profiles
from assembly_spec import build_spec
from assembly_scene_cache import SceneCache
from motherboard_catalog import MODELS,get_model,ASUS_Z790_MANUAL
from stats_config import DEFAULT

BOARD='asus-rog-strix-z790-a-wifi-d4'
SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')

class AioControlWiring051Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Software only')
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No device/network/process/thread')))
        folder=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(hardware_packs,'_store',PackStore(folder/'packs')))
    def tearDown(self):
        self.assertEqual(self.app.topLevelWindows(),[])
        self.assertIsNone(QOpenGLContext.currentContext())
    def test_exact_manual_header_roles_preserve_eight_source_positions(self):
        rows=[r for r in get_model(BOARD)['connectors'] if r['kind']=='fan']
        expected=(('CPU_OPT','cpu_opt',(.355,.014)),('CPU_FAN','cpu_fan',(.625,.014)),
          ('CHA_FAN2','case_fan',(.372,.466)),('AIO_PUMP','aio_pump',(.404,.466)),
          ('CHA_FAN1','case_fan',(.274,.985)),('CHA_FAN3','case_fan',(.724,.985)),
          ('CHA_FAN4','case_fan',(.819,.985)),('CHA_FAN5','case_fan',(.862,.985)))
        self.assertEqual(len(rows),8)
        for row,(label,role,uv) in zip(rows,expected):
            self.assertEqual((row['label'],row['role'],row['uv']),(label,role,uv))
            self.assertIs(row['role_verified'],True);self.assertEqual(row['role_source'],ASUS_Z790_MANUAL)
            self.assertEqual(row['role_source_page'],14)
        for row in MODELS:
            if row['id']!=BOARD:
                self.assertFalse(any(c.get('role_source')==ASUS_Z790_MANUAL for c in row['connectors']))
    def test_documented_seven_contact_socket_is_pierced_not_painted(self):
        builder=_Builder('balanced');meta=_lfiii_control_reference(builder,(0.,0.,0.),((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),'cooler:pump')
        socket=next(m for m in builder.finish() if m.name=='cooler-lfiii-control-seven-pin-socket')
        def hit(x,y):
            return any(_segment_triangle((x,y,16.),(x,y,26.),tuple(tuple(socket.vertices[at+k+n] for n in range(3)) for k in (0,6,12))) for at in range(0,len(socket.vertices),18))
        for i in range(7):self.assertFalse(hit((i-3)*2.,-34.))
        self.assertTrue(hit(8.,-34.));self.assertEqual(meta['cooler_connector_contacts'],7)
        self.assertEqual(meta['motherboard_connector_contacts'],4)
        anchor=builder.wire_anchors[0];self.assertTrue(anchor['lead_rendered']);self.assertNotIn('connector_rendered',anchor)
        for key in ('telemetry_bound','installed_control_mode_verified'):self.assertFalse(anchor[key]);self.assertFalse(meta[key])
    def test_added_control_geometry_keeps_existing_pump_rotors_and_450mm_hoses_identical(self):
        spec=dict(cooling=dict(cpu_cooler='arctic-liquid-freezer-iii-360',radiator_mount='top'))
        anchors=dict(cpu=dict(position=(-35.,35.,10.),normal=(-1.,0.,0.),up=(0.,1.,0.)),case_dimensions=(600.,800.,800.))
        current,meta=add_cooling((),spec,anchors=anchors)
        with patch('assembly_cooling._lfiii_control_reference',return_value={}):
            prior,oldmeta=add_cooling((),spec,anchors=anchors)
        self.assertEqual(tuple(m for m in current if not m.name.startswith('cooler-lfiii-control-')),prior)
        self.assertEqual(meta['aio_hoses'],oldmeta['aio_hoses'])
        self.assertEqual(meta['fans'],oldmeta['fans']);self.assertFalse(meta['cpu_fan_tach_usable'])
        self.assertEqual(meta['real_cpu_rotor_parts'],[])
    def test_missing_verified_cpu_fan_never_substitutes_cpu_opt_pump_or_system(self):
        source=dict(position=(0.,0.,0.),normal=(0.,1.,0.),along=(0.,0.,1.),kind='fan4',owner='cooler:pump',lead_rendered=True,role='aio_control_reference',target_header_role='cpu_fan',reference_only=True,telemetry_bound=False)
        for header in (dict(role='cpu_opt',role_verified=True),dict(role='aio_pump',role_verified=True),dict(role='case_fan',role_verified=True),dict(role='cpu_fan',role_verified=False)):
            anchor=dict(case_dimensions=(300.,300.,300.),connectors=dict(fan=[dict(position=(-80.,60.,0.),normal=(-1.,0.,0.),**header)]),cooling=dict(wire_anchors=[source]))
            meshes,meta=add_auxiliary(dict(auxiliary=dict(cables_enabled=True)),anchor)
            self.assertFalse(meshes);self.assertEqual(meta['cable_count'],0)
            self.assertEqual(meta['omitted_routes'][0]['reason'],'cpu_fan_header_unverified')
            self.assertIn('尚未核实 CPU_FAN 接口，水冷单 PWM 参考控制线未连接。',fit_messages({},dict(auxiliary=meta)))
    def test_cpu_fan_reserved_and_failed_candidate_does_not_leave_half_cables(self):
        header=lambda label,role,y:dict(position=(-80.,y,0.),normal=(-1.,0.,0.),label=label,role=role,role_verified=True)
        source=lambda role,owner,y:dict(position=(20.,y,50.),normal=(0.,1.,0.),kind='fan4',owner=owner,lead_rendered=True,role=role)
        anchors=dict(case_dimensions=(300.,300.,300.),connectors=dict(fan=[header('CPU_FAN','cpu_fan',65.),header('AIO_PUMP','aio_pump',45.),header('CHA_FAN1','case_fan',-45.)]),
          cooling=dict(wire_anchors=[source('case','fans:front:0',-40.),source('aio_control_reference','cooler:pump',20.)]))
        meshes,meta=add_auxiliary(dict(auxiliary=dict(cables_enabled=True)),anchors)
        self.assertEqual(meta['cable_count'],2)
        self.assertEqual([r['target_header_label'] for r in meta['cables']],['CPU_FAN','CHA_FAN1'])
        self.assertEqual(len({tuple(r['target_socket']) for r in meta['cables']}),2)
        self.assertFalse(any('source' in m.name for m in meshes))
        anchors['obstacles']=[dict(bounds=dict(min=(-120.,-120.,-100.),max=(120.,120.,100.)),name='solid-enclosure',part_id='foreign')]
        meshes,meta=add_auxiliary(dict(auxiliary=dict(cables_enabled=True)),anchors)
        self.assertFalse(meshes);self.assertEqual(meta['cable_count'],0);self.assertEqual(meta['omitted_route_count'],2)
        self.assertTrue(all(r['reason']=='cable_route_unavailable' for r in meta['omitted_routes']))
    def test_actual_north_and_helios_front_complete_known_control_on_six_shared_styles(self):
        engine=QQmlEngine();warnings=[];engine.warnings.connect(lambda rs:warnings.extend(r.toString() for r in rs))
        try:
            for name,updates,count,omitted in (('north',{},9,0),('helios',dict(case_model='asus-rog-strix-helios-gx601',cooler_mount='front',case_fans=[dict(model='arctic-p12-pwm',mount='top',count=2,direction='exhaust'),dict(model='arctic-p12-pwm',mount='rear',count=1,direction='exhaust')]),12,2)):
                cfg=copy.deepcopy(DEFAULT);cfg['assembly']=dict(reference_preset({},'aio'),**updates)
                spec=bake_profiles(build_spec({},cfg,{},[]),engine);cache=SceneCache()
                try:
                    scene=cache.build(spec);meta=scene.metadata;aux=meta['auxiliary'];cool=meta['cooling']
                    self.assertEqual(len(aux['cables']),count);self.assertEqual(aux['omitted_route_count'],omitted)
                    self.assertTrue(all(r['kind']=='front_io' and r['reason']=='header_capacity_unverified' for r in aux['omitted_routes']))
                    self.assertFalse(cool['connection_issues']);self.assertFalse(cool['rejected']);self.assertFalse(cool['cpu_fan_tach_usable']);self.assertEqual(cool['real_cpu_rotor_parts'],[])
                    controls=[r for r in aux['cables'] if r.get('role')=='aio_control_reference'];self.assertEqual(len(controls),1)
                    control=controls[0];self.assertEqual(control['target_header_label'],'CPU_FAN');self.assertTrue(control['target_header_role_verified'])
                    self.assertFalse(control['telemetry_bound']);self.assertFalse(control['installed_control_mode_verified'])
                    for row in aux['cables']:
                        self.assertFalse(row['external_route']);self.assertFalse(row['routing_failed'])
                        if row.get('role')=='case':self.assertTrue(row['target_header_label'].startswith('CHA_FAN'));self.assertTrue(row['preferred_waypoints_used'])
                    # Every control centerline segment clears the actual45cm
                    # hose capsules and fixed tray cells, not only their image.
                    obstacles=list(_aio_tube_obstacles(cool))+[(tuple(r['bounds']['min']),tuple(r['bounds']['max'])) for r in meta['attachment_anchors']['obstacles'] if r.get('name')=='case-motherboard-tray-reference']
                    for a,b in zip(control['path'],control['path'][1:]):
                        self.assertFalse(any(segment_hits_box(a,b,box,1.1) for box in obstacles))
                    self.assertEqual(len(cool['aio_hoses']),2);self.assertTrue(all(abs(r['centerline_length_mm']-450.)<=4.5 for r in cool['aio_hoses']))
                    self.assertEqual(meta['memory_rendered_count'],2);self.assertEqual(aux['device_counts']['psu'],1);self.assertEqual(len(meta['lighting_preview']['zones']),2)
                    physical=[m for m in scene.meshes if not m.name.startswith('style-')]
                    for style in SIX:
                        other=[m for m in cache.build(dict(spec,visual_style=style)).meshes if not m.name.startswith('style-')]
                        self.assertEqual(len(other),len(physical));self.assertTrue(all(a.vertices is b.vertices and a.position==b.position and a.axis==b.axis for a,b in zip(physical,other)))
                finally:cache.clear()
        finally:
            engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(warnings,[])

if __name__=='__main__':unittest.main()
