"""Actual H5 public host and full new cable material, not factory wire length.

The negative baseline disables only the new local policy. Both hosts use the
same fresh public spec/profile construction; no private snapshot is required.
Only the exact intended source/target attachment interfaces are exempt from
positive material checks. Other headers, the PCB, case skins and old cables
remain real obstacles. Sampled strands within one loom represent one bundle.
"""
import copy
from contextlib import ExitStack
from dataclasses import replace
import math
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

import assembly_auxiliary as auxiliary
from assembly_parts import reference_preset
from assembly_profiles import bake_profiles
from assembly_scene_cache import SceneCache
from assembly_spec import build_spec
import hardware_packs
from hardware_packs import PackStore
from stats_config import DEFAULT
from test_case_layout_hosts052 import _geometry,_overlap,_positive_overlap

H5='nzxt-h5-flow-2024'
SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def bounds(mesh):
    return tuple(tuple(fn(mesh.vertices[k::6])+mesh.position[k] for k in range(3)) for fn in (min,max))


def physical(mesh):
    return (mesh.name,mesh.vertices,mesh.color,mesh.position,mesh.component,
            mesh.rotor,mesh.direction,mesh.axis,mesh.part_id)


class H5FanLeadPolicy052Tests(unittest.TestCase):
    def endpoints(self):
        return (dict(position=(72.1,-107.4,18.),normal=(1.,0.,0.),along=(0.,-1.,0.),
            kind='fan4',owner='fans:bottom:0',role='case',connector_rendered=True),
            dict(position=(73.5,-101.425,-24.344),normal=(-1.,0.,0.),along=(0.,0.,1.),
            kind='fan4',owner='board',label='CHA_FAN3',role='case_fan',role_verified=True,
            role_source='https://dlcdnets.asus.com/manual/reference.pdf'))

    def test_unknown_wrong_case_owner_role_and_unverified_or_wrong_header_do_not_get_local_policy(self):
        source,target=self.endpoints()
        self.assertEqual(auxiliary._h5_bottom_fan_normal_lead(dict(id=H5),source,target),2.)
        for case in ({},dict(id='nzxt-h5-flow-2022'),dict(id='asus-rog-strix-helios-gx601'),None):
            self.assertIsNone(auxiliary._h5_bottom_fan_normal_lead(case,source,target))
        for changes in (dict(owner='fans:rear:0'),dict(owner='fans:bottom:99'),dict(owner='cooler:cpu'),
                dict(role='cpu_main'),dict(kind='argb3'),dict(connector_rendered=False),
                dict(normal=(-1.,0.,0.)),dict(position=(float('nan'),0.,0.))):
            self.assertIsNone(auxiliary._h5_bottom_fan_normal_lead(dict(id=H5),dict(source,**changes),target),changes)
        for changes in (dict(owner='gpu'),dict(role='cpu_fan'),dict(role_verified=False),
                dict(label='CPU_FAN'),dict(label='CHA_FAN'),dict(role_source=''),dict(kind='fan'),
                dict(normal=(1.,0.,0.))):
            self.assertIsNone(auxiliary._h5_bottom_fan_normal_lead(dict(id=H5),source,dict(target,**changes)),changes)

    def test_default_visibility_solver_contract_is_unchanged_and_invalid_leads_fail_closed(self):
        args=((0.,0.,0.),(30.,20.,0.),(1.,0.,0.),(-1.,0.,0.))
        before=auxiliary.route_cable(*args,case_dimensions=(100.,100.,100.))
        self.assertEqual(before,auxiliary.route_cable(*args,case_dimensions=(100.,100.,100.),normal_lead_mm=None))
        self.assertFalse(before[1]['routing_failed'])
        for value in (True,False,0.,-2.,1.99,2.01,100.,float('inf'),float('nan'),'2',()):
            path,state=auxiliary.route_cable(*args,normal_lead_mm=value)
            self.assertFalse(path);self.assertTrue(state['routing_failed']);self.assertFalse(state['external_route'])


class H5ActualFanRoute052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Offscreen public host only')
        cls.stack=ExitStack();cls.addClassCleanup(cls.stack.close)
        cls.cache=SceneCache();cls.old=None;cls.scene=None;cls.shapes={};cls.bounds={}
        cls.addClassCleanup(cls.release)
        folder=Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.stack.enter_context(patch.object(hardware_packs,'_store',PackStore(folder/'packs')))
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            cls.stack.enter_context(patch(target,create=True,
                side_effect=AssertionError('No sensor/device/native process/worker in H5 test')))
        cls.engine=QQmlEngine();cls.warnings=[]
        cls.engine.warnings.connect(lambda rows:cls.warnings.extend(r.toString() for r in rows))
        cls.addClassCleanup(cls.release_engine)
        cls.config=copy.deepcopy(DEFAULT);cls.config['assembly']=reference_preset({},'air')
        cls.config['assembly'].update(case_model=H5,cpu_model='intel-13700kf',gpu_model='asus-astral-5090',
            board_model='asus-rog-strix-z790-a-wifi-d4',memory_models=['gskill-f4-3200c16d-16gtzr']*2,
            psu_model='corsair-rm1000x-2024',storage=[dict(model_id='samsung-990-pro-2tb',count=1)],
            expansion_cards=[],cooler_model='noctua-nh-u12a',cooler_mount='top',
            cables_enabled=True,cable_color='black',detail_level='balanced',appearance_style='miniature',
            part_styles={},lighting_preview='mint',inspection_cutaway=True,show_psu=False,
            fan_animation=True,fan_motion='demo',case_fans=[
                dict(model='arctic-p12-pwm',mount='bottom',count=2,direction='intake'),
                dict(model='arctic-p12-pwm',mount='rear',count=1,direction='exhaust')])
        before=copy.deepcopy(cls.config)
        cls.spec=bake_profiles(build_spec({},cls.config,{},[]),cls.engine)
        old_cache=SceneCache()
        with patch.object(auxiliary,'_h5_bottom_fan_normal_lead',return_value=None):cls.old=old_cache.build(cls.spec)
        old_cache.clear()
        cls.scene=cls.cache.build(cls.spec)
        if before!=cls.config:raise AssertionError('Public build mutated configuration')

    @classmethod
    def release(cls):
        cls.shapes.clear();cls.bounds.clear();cls.old=None;cls.scene=None;cls.spec=None;cls.cache.clear()

    @classmethod
    def release_engine(cls):
        cls.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        if cls.warnings:raise AssertionError(cls.warnings)
        if cls.app.topLevelWindows() or QOpenGLContext.currentContext() is not None:
            raise AssertionError('No native window or GL context')

    def shape(self,mesh):
        if id(mesh) not in self.shapes:self.shapes[id(mesh)]=_geometry(mesh)
        return self.shapes[id(mesh)]

    def bound(self,mesh):
        if id(mesh) not in self.bounds:self.bounds[id(mesh)]=bounds(mesh)
        return self.bounds[id(mesh)]

    def assert_clear(self,first,second):
        if not _overlap(self.bound(first),self.bound(second),strict=True):return
        self.assertIsNone(_positive_overlap(self.shape(first),self.shape(second)),
            (first.name,first.part_id,second.name,second.part_id))

    def new_routes(self):
        return [row for row in self.scene.metadata['auxiliary']['cables']
            if row['source_owner'] in ('fans:bottom:0','fans:bottom:1')]

    def test_actual_two_new_power_connections_preserve_old_seven_routes_and_every_old_mesh(self):
        old=self.old.metadata['auxiliary'];new=self.scene.metadata['auxiliary']
        self.assertEqual(len(self.old.meshes),326)
        self.assertEqual(len(old['cables']),7)
        self.assertEqual(new['cables'][:7],old['cables'])
        self.assertEqual(len(new['cables']),9)
        self.assertEqual({r['source_owner'] for r in old['omitted_routes']},{'fans:bottom:0','fans:bottom:1'})
        self.assertEqual(new['omitted_routes'],[])
        self.assertFalse(any(r['external_route'] or r['routing_failed'] for r in new['cables']))
        new_routes=self.new_routes();self.assertEqual(len(new_routes),2)
        prefixes=tuple(row['mesh_prefix']+'-' for row in new_routes)
        retained=[m for m in self.scene.meshes if not m.name.startswith(prefixes)]
        self.assertEqual(len(retained),len(self.old.meshes))
        for old_mesh,current in zip(self.old.meshes,retained):
            self.assertTrue(physical(old_mesh)==physical(current),(old_mesh.name,old_mesh.part_id))
        before=self.old.metadata['attachment_anchors'];after=self.scene.metadata['attachment_anchors']
        self.assertEqual(before,after)
        self.assertEqual(self.old.metadata['cooling'],self.scene.metadata['cooling'])
        self.assertEqual(self.scene.metadata['cooling']['rejected'],[])
        self.assertEqual(sum(m.part_id=='memory:0' and m.name=='ram-pcb' for m in self.scene.meshes),1)
        self.assertEqual(sum(m.part_id=='memory:1' and m.name=='ram-pcb' for m in self.scene.meshes),1)
        for row in new_routes:
            self.assertEqual(row['kind'],'fan4');self.assertEqual(row['target_owner'],'board')
            self.assertTrue(row['target_header_role_verified']);self.assertEqual(row['target_header_role'],'case_fan')
            self.assertTrue(row['target_header_label'].startswith('CHA_FAN'))
            source=next(r for r in after['cooling']['wire_anchors'] if r['owner']==row['source_owner'])
            target=next(r for r in after['connectors']['fan'] if r['label']==row['target_header_label'])
            self.assertEqual(row['source_socket'],source['position']);self.assertEqual(row['target_socket'],target['position'])
            self.assertEqual(row['start'],source['position'])
            self.assertEqual(row['end'],auxiliary._add(target['position'],auxiliary._mul(target['normal'],9.)))
            self.assertEqual(row['routing_reference_normal_lead_mm'],2.)
            self.assertFalse(row['connector_lead_manufacturer_verified']);self.assertFalse(row['factory_cable_length_modeled'])
            self.assertEqual(row['routing_policy'],'h5_bottom_header_main_chamber_reference')
            for suffix in ('target-plug-shell','target-plug-pins','rounded-loom'):
                self.assertEqual(sum(m.name==row['mesh_prefix']+'-'+suffix for m in self.scene.meshes),1)

    def test_new_real_plugs_pins_and_looms_clear_326_old_entities_and_each_other_route(self):
        routes=self.new_routes();self.assertEqual(len(routes),2)
        groups=[]
        for row in routes:
            pieces=[m for m in self.scene.meshes if m.name.startswith(row['mesh_prefix']+'-')]
            self.assertEqual(len(pieces),3)
            target=row['target_socket']
            mating=[m for m in self.old.meshes if m.component=='board' and m.position==target
                and m.name in ('board-header-fan','board-header-pins')]
            self.assertEqual({m.name for m in mating},{'board-header-fan','board-header-pins'})
            for piece in pieces:
                for old in self.old.meshes:
                    # A plug occupies only its exact socket/pins. No other
                    # board body/header is waived, including nearby CHA pins.
                    if piece.name.endswith(('target-plug-shell','target-plug-pins')) and old in mating:continue
                    if (piece.name.endswith('rounded-loom') and old.name=='case-fan-power-connector'
                            and old.part_id==row['source_owner']):continue
                    with self.subTest(route=row['source_owner'],new=piece.name,old=old.name,part=old.part_id):
                        self.assert_clear(piece,old)
            groups.append(pieces)
        for first in groups[0]:
            for second in groups[1]:self.assert_clear(first,second)
        # This is a real non-mating body regression: a plug on the crowded
        # last CHA socket hits its neighbour. It must not be selected just
        # because its loom alone fits. The selected targets clear all bodies.
        headers=self.scene.metadata['attachment_anchors']['connectors']['fan']
        rejected=[r for r in headers if r.get('role')=='case_fan' and not auxiliary._fan_plug_clears_neighbor_headers(r,headers)]
        self.assertTrue(rejected)
        self.assertTrue(all(r['target_socket'] not in [h['position'] for h in rejected] for r in routes))

    def test_a_bad_local_route_is_vetoed_and_rolls_back_to_complete_old_omissions(self):
        original=auxiliary.route_cable;injected=[]
        def bad_local(start,end,sn,en,*args,**kwargs):
            if kwargs.get('normal_lead_mm') is not None:
                injected.append(start)
                # The existing final per-strand checks must veto this path;
                # merely lying about the central routing state cannot add it.
                return (start,(95.8,start[1],start[2]),end),dict(routing_failed=False,
                    external_route=False,preferred_waypoints_used=False)
            return original(start,end,sn,en,*args,**kwargs)
        cache=SceneCache()
        try:
            with patch.object(auxiliary,'route_cable',side_effect=bad_local):failed=cache.build(self.spec)
            self.assertTrue(injected)
            self.assertEqual(failed.metadata['auxiliary']['cables'],self.old.metadata['auxiliary']['cables'])
            self.assertEqual({r['source_owner'] for r in failed.metadata['auxiliary']['omitted_routes']},
                             {'fans:bottom:0','fans:bottom:1'})
            self.assertEqual(len(failed.meshes),326)
            for old,current in zip(self.old.meshes,failed.meshes):
                self.assertTrue(physical(old)==physical(current),(old.name,old.part_id))
        finally:cache.clear()

    def test_all_six_actual_styles_reuse_final_physical_arrays_without_extra_builds(self):
        base=[m for m in self.scene.meshes if not m.name.startswith('style-')]
        base_key=self.cache.key
        for style in SIX:
            value=self.cache.build(dict(self.spec,visual_style=style))
            self.assertEqual(self.cache.key,base_key)
            rows=[m for m in value.meshes if not m.name.startswith('style-')]
            self.assertEqual(len(base),len(rows))
            for old,current in zip(base,rows):
                self.assertIs(old.vertices,current.vertices)
                self.assertEqual((old.name,old.part_id,old.position,old.rotor,old.direction,old.axis),
                                 (current.name,current.part_id,current.position,current.rotor,current.direction,current.axis))


if __name__=='__main__':unittest.main()
