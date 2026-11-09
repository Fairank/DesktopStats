"""Actual controller/standalone QML requests, with no native or GL window."""
import copy
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QCoreApplication,QEvent,QObject,QUrl
from PySide6.QtQml import QQmlComponent,QQmlEngine
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

import native_controller as controls
from stats_config import DEFAULT

ROOT=Path(__file__).resolve().parents[1]


class AssemblyDesktopControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        assert cls.app.platformName()=='offscreen'

    def setUp(self):
        self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native query')))
        self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No processes')))
        self.enterContext(patch.object(controls,'load',return_value=copy.deepcopy(DEFAULT)))
        self.enterContext(patch('chassis_identity.snapshot',return_value={'state':'unavailable'}))
        self.enterContext(patch('memory_identity.modules',return_value=[]))
        self.ui=controls.Controller();self.ui.setAssemblyActive(True)

    def tearDown(self):
        self.ui.close();self.ui.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_desktop_and_inspection_are_detached_requests_in_preferences_scope(self):
        before=copy.deepcopy(self.ui.draft);spy=QSignalSpy(self.ui.assemblyViewRequested)
        self.ui.changeAssembly('desktop_frame',False)
        self.ui.openAssemblyDesktop()
        self.assertEqual(spy.count(),1)
        self.assertEqual(spy.at(0)[0]['options']['window_mode'],'desktop')
        self.assertFalse(spy.at(0)[0]['options']['desktop_frame'])
        spy.at(0)[0]['case']['label']='detached'
        self.assertNotEqual(self.ui.assembly_specification()['case']['label'],'detached')
        self.assertEqual(self.ui.draft['top_bar'],before['top_bar'])
        self.assertEqual(self.ui.draft['widgets'],before['widgets'])
        self.assertEqual(self.ui.scopeDirty,dict(desktop=False,preferences=True,topbar=False))
        self.ui.openAssemblyInspect()
        self.assertEqual(spy.count(),2)
        self.assertEqual(spy.at(1)[0]['options']['window_mode'],'inspect')
        self.assertFalse(spy.at(1)[0]['options']['desktop_frame'])

    def test_actual_qml_buttons_and_frame_toggle_reach_the_controller(self):
        engine=QQmlEngine();warnings=[]
        engine.warnings.connect(lambda rows:warnings.extend(row.toString() for row in rows))
        engine.rootContext().setContextProperty('stats',self.ui)
        component=QQmlComponent(engine,QUrl.fromLocalFile(str(ROOT/'native/AssemblyPage.qml')))
        page=component.createWithInitialProperties(dict(active=True,width=720,height=800))
        self.assertIsNotNone(page,[e.toString() for e in component.errors()])
        try:
            spy=QSignalSpy(self.ui.assemblyViewRequested)
            desktop=page.findChild(QObject,'openAssemblyDesktopButton')
            inspect=page.findChild(QObject,'openAssemblyInspectButton')
            frame=page.findChild(QObject,'assemblyDesktopFrameToggle')
            self.assertTrue(desktop.property('enabled'));self.assertTrue(inspect.property('enabled'))
            desktop.clicked.emit();self.assertEqual(spy.at(0)[0]['options']['window_mode'],'desktop')
            frame.setProperty('checked',False);frame.toggled.emit()
            self.assertFalse(self.ui.draft['assembly']['desktop_frame'])
            inspect.clicked.emit();self.assertEqual(spy.at(1)[0]['options']['window_mode'],'inspect')
            self.assertEqual(warnings,[])
        finally:
            page.deleteLater();component.deleteLater()
            QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
            engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


if __name__=='__main__':unittest.main()
