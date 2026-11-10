"""Real Runtime gate bodies and guard protocol, with no Qt or native calls."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

from secondary_window_guard055 import (
    SecondaryWindowGuard, Token, WINDOWPOS, HIDE, SHOW, NOACTIVATE, NOZORDER,
)

ROOT=Path(__file__).resolve().parents[1]
TARGET=r'\\.\DISPLAY37'
PRIMARY=r'\\.\DISPLAY36'
WORK=(2560,-509,4000,1971)


def method(name,scope,*,restore_current_screen_gate=False):
    tree=ast.parse((ROOT/'native_runtime.py').read_text('utf-8'))
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef)and node.name=='Runtime')
    node=copy.deepcopy(next(node for node in cls.body if isinstance(node,ast.FunctionDef)and node.name==name))
    if restore_current_screen_gate:
        assert name=='_secondary_window_context' and isinstance(node.body[-1],ast.Return)
        node.body.insert(-1,ast.parse(
            'if secondary_screen_id(window.screen()).casefold()!=identity.native_id.casefold():return None').body[0])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                 'native_runtime.py::<actual secondary gate>','exec'),scope)
    return scope[name]


class Window:
    def __init__(self):self.visible=False;self.hides=0;self.qt_screen=PRIMARY
    def isTopLevel(self):return True
    def isVisible(self):return self.visible
    def hide(self):self.hides+=1;self.visible=False
    def screen(self):return self.qt_screen


class Api:
    def __init__(self):
        self.value=dict(rect=(640,316,1920,1076),native_id=PRIMARY,minimized=False)
    def attach(self,hwnd,generation,pid,thread):return Token(hwnd,pid,thread,'Stats',generation)
    def state(self,token):return dict(self.value)
    def valid(self,token):return True
    def release(self,token):pass
    def apply(self,position,native_id):
        self.value=dict(rect=(position.x,position.y,position.x+position.cx,position.y+position.cy),
                        native_id=native_id,minimized=False)


class Bridge:
    def start(self,guard):pass
    def watch(self,window,guard):pass
    def unwatch(self,window):pass
    def stop(self):pass


def fixture(*,admitted=True,missing_target=False,old_condition=False):
    runtime_class=type('Runtime',(),{})
    runtime_class._secondary_admitted=lambda self:admitted
    target=object()
    runtime_class._secondary_screen=lambda self:None if missing_target else target
    api=Api();window=Window()
    scope=dict(Runtime=runtime_class,secondary_active=lambda:True,
               secondary_screen_id=lambda screen:screen)
    context=method('_secondary_window_context',scope,restore_current_screen_gate=old_condition)
    runtime_class._secondary_window_context=context
    runtime_class._secondary_window_admitted=method('_secondary_window_admitted',scope)
    runtime=runtime_class()
    calls=[]
    def screen_identity(screen):
        calls.append(screen)
        assert screen is target,'Only the configured target supplies the placement region'
        return SimpleNamespace(native_id=TARGET,monitor_handle=37)
    runtime.top_bar=SimpleNamespace(adapter=SimpleNamespace(screen_identity=screen_identity,
        _monitor_info=lambda handle:SimpleNamespace(rcWork=SimpleNamespace(
            **dict(zip(('left','top','right','bottom'),WORK))))))
    guard=SecondaryWindowGuard(api,Bridge(),lambda owner:context(runtime,owner),pid=1,native_thread=2)
    runtime._secondary_window_guard=guard
    assert guard.watch(window)and guard.bind(window,100)
    return SimpleNamespace(runtime=runtime,guard=guard,api=api,window=window,calls=calls)


class SecondaryBootstrapPosition055Tests(unittest.TestCase):
    def test_hidden_primary_owner_can_move_but_cannot_pass_show_gate_before_native_move(self):
        case=fixture()
        self.assertEqual(case.runtime._secondary_window_context(case.window),
                         dict(admitted=True,native_id=TARGET,work=WORK))
        self.assertFalse(case.runtime._secondary_window_admitted(case.window))
        position=WINDOWPOS(hwnd=100,x=2640,y=351,cx=1280,cy=640,flags=NOACTIVATE|NOZORDER)
        self.assertEqual(case.guard.native_message(100,0x46,position),(True,0))
        self.assertFalse(position.flags&HIDE)
        self.assertTrue(position.flags&NOACTIVATE)
        self.assertEqual((position.x,position.y),(2640,351))
        self.assertFalse(case.runtime._secondary_window_admitted(case.window))
        case.api.apply(position,TARGET)
        self.assertTrue(case.runtime._secondary_window_admitted(case.window))
        # A Qt screen notification may lag the real native placement. Actual
        # Windows monitor and complete frame bounds determine Show admission.
        self.assertEqual(case.window.screen(),PRIMARY)
        case.api.value['rect']=(2640,351,4001,991)
        self.assertFalse(case.runtime._secondary_window_admitted(case.window))
        case.api.value.update(rect=(2640,351,3920,991),native_id=PRIMARY)
        self.assertFalse(case.runtime._secondary_window_admitted(case.window))
        case.guard.close()

    def test_unknown_target_or_desktop_rejects_pending_move_and_show(self):
        for options in (dict(admitted=False),dict(missing_target=True)):
            with self.subTest(options=options):
                case=fixture(**options)
                self.assertIsNone(case.runtime._secondary_window_context(case.window))
                position=WINDOWPOS(hwnd=100,x=2640,y=351,cx=1280,cy=640,
                                   flags=SHOW|NOACTIVATE|NOZORDER)
                self.assertEqual(case.guard.native_message(100,0x46,position),(True,0))
                self.assertTrue(position.flags&HIDE)
                self.assertFalse(position.flags&SHOW)
                self.assertFalse(case.runtime._secondary_window_admitted(case.window))
                self.assertEqual(case.calls,[])
                case.guard.close()

    def test_confirmed_target_clamps_pending_show_while_old_current_screen_gate_deadlocks(self):
        case=fixture()
        position=WINDOWPOS(hwnd=100,x=640,y=316,cx=1280,cy=760,
                           flags=SHOW|NOACTIVATE|NOZORDER)
        case.guard.native_message(100,0x46,position)
        self.assertTrue(position.flags&SHOW)
        self.assertFalse(position.flags&HIDE)
        self.assertTrue(WORK[0]<=position.x and position.x+position.cx<=WORK[2])
        self.assertTrue(WORK[1]<=position.y and position.y+position.cy<=WORK[3])
        self.assertFalse(case.runtime._secondary_window_admitted(case.window))
        case.api.apply(position,TARGET)
        self.assertTrue(case.runtime._secondary_window_admitted(case.window))
        case.guard.close()
        old=fixture(old_condition=True)
        move=WINDOWPOS(hwnd=100,x=2640,y=351,cx=1280,cy=640,flags=NOACTIVATE|NOZORDER)
        old.guard.native_message(100,0x46,move)
        self.assertTrue(move.flags&HIDE)
        self.assertFalse(move.flags&SHOW)
        self.assertFalse(old.runtime._secondary_window_admitted(old.window))
        old.guard.close()


if __name__=='__main__':unittest.main()
