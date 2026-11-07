"""Desktop cards load on first use without introducing a background compiler."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QUrl
from native_runtime import Runtime


class LazyDesktopWidgetTests(unittest.TestCase):
    def test_bar_updates_and_headless_apply_do_not_compile_desktop_cards(self):
        runtime=SimpleNamespace(top_bar=Mock(),controller=SimpleNamespace(_saved={}),
            update_menu=Mock(),headless=True,desktop_widget_component=Mock())
        Runtime.apply_top_bar(runtime)
        Runtime.apply(runtime)
        runtime.desktop_widget_component.assert_not_called()

    def test_first_desktop_request_compiles_once_and_reuses_for_later_cards(self):
        runtime=SimpleNamespace(component=None,engine=object())
        component=Mock();component.isError.return_value=False
        with patch('native_runtime.QQmlComponent',return_value=component) as compile_card:
            self.assertIs(Runtime.desktop_widget_component(runtime),component)
            self.assertIs(Runtime.desktop_widget_component(runtime),component)
            compile_card.assert_called_once()
            self.assertIs(compile_card.call_args.args[0],runtime.engine)
            self.assertTrue(compile_card.call_args.args[1].toLocalFile().endswith('DesktopWidget.qml'))

    def test_failed_compilation_reports_cause_without_caching_broken_component(self):
        runtime=SimpleNamespace(component=None,engine=object())
        broken=Mock();broken.isError.return_value=True
        broken.errors.return_value=[SimpleNamespace(toString=lambda:'fixture.qml:12: unknown type')]
        with patch('native_runtime.QQmlComponent',return_value=broken):
            with self.assertRaisesRegex(RuntimeError,'fixture.qml:12: unknown type'):
                Runtime.desktop_widget_component(runtime)
        self.assertIsNone(runtime.component)

    def test_runtime_initialization_does_not_eagerly_construct_desktop_qml(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'native_runtime.py').read_text(encoding='utf8'))
        init=next(n for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='Runtime'
                  for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                             and n.func.id=='QQmlComponent' for n in ast.walk(init)))


if __name__=='__main__':unittest.main()
