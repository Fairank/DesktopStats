"""Manual, single-model 3D inspection of separately licensed open references.

Import only after an explicit user request and the host's foreground/screen
guard. Construction never shows a window, opens a file, samples hardware,
subscribes to readings, starts a clock or downloads an asset. Original
application code follows LICENSE; loaded assets keep their own notices.
"""
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,
                               QPushButton,QCheckBox,QSizePolicy)


STYLES=(('miniature','原版'),('cartoon','可爱笑脸'),
        ('notebook_color','彩色手绘'),('notebook_line','纯线条'),
        ('sticker','奶油贴纸'),('papercut','拼色剪纸'))


def _text(value):
    if isinstance(value,str):return value
    if isinstance(value,(tuple,list)):return ' · '.join(str(item) for item in value)
    return str(value or '')


class OpenReferenceWindow(QWidget):
    """A real depth-tested mesh view, with no autonomous rendering loop.

    Runtime owns the existing target-screen/fullscreen guard and calls the
    compatibility no-ops below. It decides when this manual window may show.
    The model contains no monitored-hardware identity or mechanical fit claim.
    """
    closed=Signal()
    window_mode='reference'

    def __init__(self,model,controller=None,parent=None,*,viewport_factory=None):
        super().__init__(parent)
        self.controller=controller
        self._model=model;self._styled_scene=None
        self._closing=False;self._guard_hidden=False;self._synchronizing=False
        self._renderer_failed=False
        self.setAttribute(Qt.WA_DeleteOnClose,True)
        self.setAttribute(Qt.WA_ShowWithoutActivating,True)
        self.setWindowTitle('开源硬件检视 · Desktop Stats')
        self.resize(980,700);self.setMinimumSize(700,500)
        self.setProperty('modelMotionAllowed',False)
        try:
            self._build(model,viewport_factory)
        except BaseException:
            self._dispose()
            self.deleteLater()
            raise

    def _tr(self,value):
        translate=getattr(self.controller,'tr',None)
        return translate(value) if callable(translate) else value

    def _build(self,model,viewport_factory):
        if viewport_factory is None:
            from assembly_viewer import AssemblyViewport
            viewport_factory=AssemblyViewport
        dark=getattr(self.controller,'theme','light')=='dark'
        ink='#e9eef3' if dark else '#263b49'
        background='#202832' if dark else '#f3f6f7'
        border='#4c5b68' if dark else '#c8d3d9'
        self.setStyleSheet(
            'QWidget{font-family:"Segoe UI","Microsoft YaHei UI";font-size:12px;'
            'color:'+ink+';background:'+background+';}'
            'QComboBox,QPushButton{padding:7px 10px;border:1px solid '+border+';'
            'border-radius:6px;}'
            'QLabel{background:transparent;}')
        layout=QVBoxLayout(self);layout.setContentsMargins(18,16,18,14);layout.setSpacing(10)
        header=QHBoxLayout()
        self.title=QLabel(_text(model.label));self.title.setTextFormat(Qt.PlainText)
        self.title.setObjectName('openReferenceTitle')
        self.title.setStyleSheet('font-size:20px;font-weight:600;')
        self.title.setWordWrap(True);self.title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        header.addWidget(self.title,1)
        self.style_choice=QComboBox();self.style_choice.setObjectName('openReferenceStyle')
        self.style_choice.setAccessibleName(self._tr('外观风格'));self.style_choice.setMinimumWidth(142)
        for identity,label in STYLES:self.style_choice.addItem(self._tr(label),identity)
        header.addWidget(self.style_choice)
        layout.addLayout(header)

        hint=QLabel(self._tr('拖动旋转 · 滚轮缩放 · 单击选择部件'))
        hint.setObjectName('openReferenceHint');hint.setWordWrap(True)
        layout.addWidget(hint)
        controls=QHBoxLayout();controls.setSpacing(8)
        self.part_choice=QComboBox();self.part_choice.setObjectName('openReferencePart')
        self.part_choice.setAccessibleName(self._tr('查看部件'))
        self.part_choice.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.part_choice.addItem(self._tr('全部部件'),'all')
        self._part_ids={'all'}
        for part in model.parts:
            identity=part['id']
            if not isinstance(identity,str) or not identity.startswith('reference:') or identity in self._part_ids:
                raise ValueError('Distinct reviewed reference part identities are required')
            self._part_ids.add(identity);self.part_choice.addItem(_text(part['label']),identity)
        controls.addWidget(self.part_choice,1)
        self.focus_selected=QCheckBox(self._tr('只看所选'));self.focus_selected.setObjectName('openReferenceFocus')
        self.focus_selected.setEnabled(False)
        controls.addWidget(self.focus_selected)
        self.hide_selected=QCheckBox(self._tr('隐藏所选'));self.hide_selected.setObjectName('openReferenceHide')
        self.hide_selected.setEnabled(False)
        controls.addWidget(self.hide_selected)
        self.restore_button=QPushButton(self._tr('恢复部件'));self.restore_button.setObjectName('openReferenceRestore')
        controls.addWidget(self.restore_button)
        self.reset_button=QPushButton(self._tr('恢复视角'));self.reset_button.setObjectName('openReferenceCamera')
        controls.addWidget(self.reset_button)
        layout.addLayout(controls)

        self.viewport=viewport_factory(self,reference_scene=model.scene)
        self.viewport.setObjectName('openReferenceViewport')
        self.viewport.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.viewport.set_dark(dark);self.viewport.set_motion_enabled(False)
        self.viewport.set_selection_effects_enabled(False)
        self.viewport.set_fan_animation_enabled(False)
        layout.addWidget(self.viewport,1)
        self._styled_scene=model.scene
        self.status=QLabel(self._tr('独立参考 · 简化材质 · 不绑定本机读数；隐藏仅用于检视。'))
        self.status.setObjectName('openReferenceStatus');self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        self.attribution=QLabel(_text(model.attribution));self.attribution.setWordWrap(True)
        self.attribution.setObjectName('openReferenceAttribution');self.attribution.setTextFormat(Qt.PlainText)
        self.attribution.setStyleSheet('font-size:11px;')
        self.attribution.setToolTip('\n'.join(_text(item) for item in model.source_urls))
        layout.addWidget(self.attribution)
        self.status.setToolTip(_text(model.material_limits))

        self.style_choice.currentIndexChanged.connect(self._change_style)
        self.part_choice.currentIndexChanged.connect(self._choose_part)
        self.focus_selected.toggled.connect(self._focus_part)
        self.hide_selected.toggled.connect(self._hide_part)
        self.restore_button.clicked.connect(self._restore_parts)
        self.reset_button.clicked.connect(self._reset_camera)
        self.viewport.componentSelected.connect(self._picked_part)
        self.viewport.rendererError.connect(self._renderer_error)
        self._choose_part()

    def _can_interact(self):
        return (not self._closing and not self._guard_hidden and not self._renderer_failed
                and self.isVisible() and not self.isMinimized()
                and self.property('modelMotionAllowed') is not False)

    def _change_style(self,_index):
        if not self._can_interact() or self._model is None:return
        style=self.style_choice.currentData()
        if style not in {identity for identity,_ in STYLES}:return
        from open_reference_models054 import scene_for_style
        try:
            scene=scene_for_style(self._model,style)
            self.viewport.set_reference_scene(scene)
            self._styled_scene=scene
        except Exception:
            self._renderer_error(self._tr('此参考外观暂时无法显示。'))

    def _choose_part(self,_index=None):
        if self._synchronizing or not self._can_interact():return
        target=self.part_choice.currentData() or 'all'
        if target not in self._part_ids:return
        self._synchronizing=True
        try:
            self.viewport.select_component(target)
            selected=target!='all'
            self.hide_selected.setEnabled(selected);self.focus_selected.setEnabled(selected)
            self.hide_selected.setChecked(target in getattr(self.viewport,'_hidden_parts',()))
        finally:self._synchronizing=False
        self.viewport.focus_component(target if self.focus_selected.isChecked() and target!='all' else 'all')

    def _picked_part(self,target):
        if self._synchronizing or not self._can_interact() or target not in self._part_ids:return
        index=self.part_choice.findData(target)
        if index>=0:
            if index==self.part_choice.currentIndex():self._choose_part()
            else:self.part_choice.setCurrentIndex(index)

    def _focus_part(self,enabled):
        if self._synchronizing or not self._can_interact():return
        target=self.part_choice.currentData() or 'all'
        self.viewport.focus_component(target if enabled and target in self._part_ids else 'all')

    def _hide_part(self,enabled):
        if self._synchronizing or not self._can_interact():return
        target=self.part_choice.currentData()
        if target in self._part_ids and target!='all':self.viewport.set_part_hidden(target,enabled is True)

    def _restore_parts(self):
        if not self._can_interact():return
        self.viewport.restore_hidden_parts()
        self._synchronizing=True
        try:self.hide_selected.setChecked(False)
        finally:self._synchronizing=False

    def _reset_camera(self):
        if self._can_interact():self.viewport.reset_camera()

    def _renderer_error(self,_message):
        self._renderer_failed=True
        self.status.setText(self._tr('此设备暂时无法显示该三维参考；可以关闭窗口后重试。'))
        self.style_choice.setEnabled(False);self.part_choice.setEnabled(False)
        self.focus_selected.setEnabled(False);self.hide_selected.setEnabled(False)
        self.restore_button.setEnabled(False);self.reset_button.setEnabled(False)

    def _clock_active(self,_active):
        # Runtime compatibility only: this window owns no clock or subscription.
        return False

    def update_readings(self):
        # There are deliberately no live readings in an independent reference.
        return None

    def set_guard_hidden(self,hidden):
        if type(hidden) is not bool:return
        self._guard_hidden=hidden
        if hidden:
            self._close_owned_popups()
            self.viewport.set_motion_enabled(False)
            self.hide()
        # Only Runtime's target-screen guard may show the window again.

    def _close_owned_popups(self):
        for name in ('style_choice','part_choice'):
            control=getattr(self,name,None)
            if control is not None:control.hidePopup()

    def hideEvent(self,event):
        self._close_owned_popups()
        super().hideEvent(event)

    def _dispose(self):
        if self._closing:return
        self._closing=True;self._close_owned_popups()
        viewport=getattr(self,'viewport',None)
        try:
            if viewport is not None:viewport.close()
        except Exception as error:
            # ReferenceViewport retires CPU arrays in a finally block even if
            # a lost GL context cannot delete its native handles immediately.
            self._close_error=str(error)[:160]
        finally:
            self._model=None;self._styled_scene=None

    def closeEvent(self,event):
        try:self._dispose()
        finally:self.closed.emit();event.accept()
