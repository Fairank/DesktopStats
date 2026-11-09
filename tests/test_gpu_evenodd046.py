"""Preserve the reviewed compound front shell without cutting later details."""
import copy
import math
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent,QPointF
from PySide6.QtGui import QGuiApplication,QPainterPath,QPolygonF
from PySide6.QtQml import QQmlEngine

from assembly_profiles import ProfileReader,bake_profiles,bounds,path_polygon,_shell_holes,_fan_radius
from hardware_appearance import CATALOG,appearance_for
from top_bar_config import HARDWARE_ICON_STYLES


def _appearance(identity):
    row=next(row for row in CATALOG if row[0]==identity)
    value=appearance_for(row[1],row[-1][0])
    assert value['id']==identity
    return value


def _contains(points,point):
    path=QPainterPath()
    path.addPolygon(QPolygonF([QPointF(*v) for v in points]));path.closeSubpath()
    return path.contains(QPointF(*point))


def _spec(appearance):
    return dict(gpu=dict(appearance=appearance,width_mm=120),
                cpu=dict(appearance=_appearance('intel-13700kf')),memory=dict(modules=[]))


class GpuEvenodd046Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','socket.socket','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No external/native/thread work')))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda values:self.warnings.extend(v.toString() for v in values))
        self.reader=ProfileReader(self.engine)

    def tearDown(self):
        self.reader.close();self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(self.warnings,[])

    def test_actual_reviewed_shell_retains_its_explicit_evenodd_semantics(self):
        profile=self.reader.read(_appearance('gigabyte-windforce-4060-oc'))
        self.assertEqual(profile['shell']['fill_rule'],'evenodd')
        self.assertEqual(profile['shell']['d'].count('M'),2)
        self.assertEqual(len(path_polygon(profile['shell'])),12)
        holes=_shell_holes(profile['shell']);self.assertEqual(len(holes),1)
        self.assertEqual(len(holes[0]),4)
        for actual,expected in zip(bounds(holes[0]),(4.066,10.171,16.168,2.958)):
            self.assertAlmostEqual(actual,expected,places=6)

    def test_window_and_independently_drawn_bridge_are_not_the_same_mask(self):
        before=_spec(_appearance('gigabyte-windforce-4060-oc'));saved=copy.deepcopy(before)
        gpu=bake_profiles(before,self.engine)['gpu']
        self.assertEqual(before,saved)
        expected=[[[.07,.27027],[.07,.72973],[.93,.72973],[.93,.27027]]]
        self.assertEqual(gpu['shell_holes'],expected)
        for point in ((.56,.5),(.46,.5)):
            self.assertTrue(_contains(gpu['shell_polygon'],point))
            self.assertTrue(_contains(gpu['shell_holes'][0],point))
        self.assertFalse(any(_contains(d['points'],(.56,.5)) for d in gpu['detail_polygons']))
        self.assertTrue(_contains(gpu['detail_polygons'][0]['points'],(.46,.5)))
        self.assertTrue(all('holes' not in d and 'shell_holes' not in d for d in gpu['detail_polygons']))
        self.assertNotIn('shell_holes',bake_profiles(before,self.engine)['cpu'])

    def test_plain_or_disconnected_paths_do_not_invent_apertures(self):
        plain=dict(d='M0 0H10V10H0Z M2 2H8V8H2Z',m=[1,0,0,1,0,0])
        self.assertEqual(_shell_holes(plain),[])
        self.assertEqual(_shell_holes(dict(plain,fill_rule='nonzero')),[])
        disconnected=dict(d='M0 0H10V10H0Z M12 2H14V4H12Z',fill_rule='evenodd')
        self.assertEqual(_shell_holes(disconnected),[])
        nested=dict(d='M0 0H10V10H0Z M2 2H8V8H2Z M3 3H4V4H3Z',fill_rule='evenodd')
        self.assertEqual(_shell_holes(nested),[])

    def test_stale_hole_is_removed_when_another_card_is_selected(self):
        spec=_spec(_appearance('asus-astral-5090'))
        spec['gpu']['shell_holes']=[[[0,0],[1,0],[1,1]]]
        result=bake_profiles(spec,self.engine)
        self.assertNotIn('shell_holes',result['gpu'])
        self.assertIn('shell_holes',spec['gpu'])
        self.assertNotIn('fill_rule',self.reader.read(spec['gpu']['appearance'])['shell'])

    def test_all_existing_styles_share_the_same_compound_geometry(self):
        base=_spec(_appearance('gigabyte-windforce-4060-oc'));reference=None
        for style in HARDWARE_ICON_STYLES:
            spec=copy.deepcopy(base);spec['visual_style']=style
            gpu=bake_profiles(spec,self.engine)['gpu']
            if reference is None:reference=gpu
            self.assertEqual(gpu,reference)

    def test_all_147_gpu_fans_keep_source_identity_and_use_both_reference_axes(self):
        count=0
        for row in CATALOG:
            if row[1]!='gpu':continue
            count+=1;appearance=_appearance(row[0]);source=self.reader.read(appearance)
            spec=_spec(appearance)
            dims=appearance.get('board_details',{}).get('dimensions_mm') or {}
            spec['gpu'].update(length_mm=dims.get('length'),width_mm=dims.get('height'))
            gpu=bake_profiles(spec,self.engine)['gpu']
            shell=path_polygon(source.get('shell'));box=source['bounds']
            x,y,w,h=bounds(shell) if shell else (box['x'],box['y'],box['width'],box['height'])
            self.assertEqual(gpu['physical_fan_count'],source['physical_fan_count'])
            self.assertEqual(len(gpu['fans']),len(source['fans']))
            for raw,fan in zip(source['fans'],gpu['fans']):
                with self.subTest(model=row[0],fan=raw['cx']):
                    self.assertEqual(fan['radius_uv'],[raw['radius']/w,raw['radius']/h])
                    self.assertEqual(fan['center_uv'],[(raw['cx']-x)/w,(raw['cy']-y)/h])
                    self.assertEqual(fan['profile'],raw['profile'])
                    self.assertEqual(fan['direction'],raw['direction'])
                    self.assertEqual(fan['blades'],raw['profile'].get('blades'))
                    self.assertEqual(fan['hub_ratio'],raw['hub_ratio'])
                    self.assertEqual(fan['colors'],raw['colors'])
                    length,width=dims.get('length'),dims.get('height')
                    if (type(length) in (int,float) and math.isfinite(length) and 80<=length<=450
                            and type(width) in (int,float) and math.isfinite(width) and 50<=width<=190):
                        old=raw['radius']/h*width
                        base=old if 5<=old<=75 else min(width*.41,length/max(1,len(source['fans']))*.42)
                        u,v=raw['radius']/w,raw['radius']/h
                        expected=min((u if .005<=u<=.5 else base/length)*length,
                                     (v if .005<=v<=.5 else base/width)*width)
                        self.assertAlmostEqual(fan['radius_mm'],expected,places=10)
        self.assertEqual(count,148)

    def test_unknown_physical_axis_keeps_scalar_fallback_without_claiming_fan_diameter(self):
        self.assertEqual(_fan_radius([.18,.52],63.2,None,120,2),63.2)
        self.assertEqual(_fan_radius([.18,.52],63.2,192,None,2),63.2)
        self.assertAlmostEqual(_fan_radius([.18,.52],63.2,192,120,2),34.56)
        self.assertAlmostEqual(_fan_radius([.18,.52],float('nan'),192,120,2),34.56)


if __name__=='__main__':unittest.main()
