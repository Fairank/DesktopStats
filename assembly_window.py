"""Owned, on-demand 3D window; closed windows retain no graphics or clock."""
import copy
import json
import time

from PySide6.QtCore import Qt, Signal, Slot, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QCheckBox,QComboBox)

from assembly_profiles import bake_profiles
from stats_config import ASSETS
from top_bar_feedback import GPU_FAN_MAX_AGE


class AssemblyWindow(QWidget):
    closed=Signal()

    def __init__(self,controller,engine,spec,*,viewport_factory=None):
        super().__init__()
        self.controller=controller;self.engine=engine;self._closing=False
        self._clock=None;self._clock_component=None;self._connections=[];self._viewer_active=False
        try:
            self._initialize(controller,engine,spec,viewport_factory)
        except Exception:
            self._dispose()
            self.deleteLater()
            raise

    def _initialize(self,controller,engine,spec,viewport_factory):
        if viewport_factory is None:
            from assembly_viewer import AssemblyViewport
            viewport_factory=AssemblyViewport
        self._geometry_key=None;self._last_fan={};self._spec=None;self._renderer_error=False
        self.setAttribute(Qt.WA_DeleteOnClose,True)
        self.setWindowTitle(controller.tr("整机视图")+" · Desktop Stats")
        self.resize(1080,780);self.setMinimumSize(760,520)
        dark=controller.theme=="dark"
        self.setStyleSheet("QWidget{font-family:'Segoe UI','Microsoft YaHei UI';font-size:12px;color:"
            +("#e8edf2;background:#202731" if dark else "#293945;background:#f0f4f7")
            +";} QPushButton,QComboBox{padding:7px 12px;border:1px solid "
            +("#52606e" if dark else "#c8d2db")+";border-radius:6px;} QPushButton:hover{background:"
            +("#34404c" if dark else "#e2eaf0")+";}")
        layout=QVBoxLayout(self);layout.setContentsMargins(18,16,18,14);layout.setSpacing(12)
        header=QHBoxLayout();self.title=QLabel();self.title.setTextFormat(Qt.PlainText)
        self.title.setStyleSheet("font-size:19px;font-weight:600;")
        header.addWidget(self.title,1)
        self.focus_choice=QComboBox();self.focus_choice.setAccessibleName(controller.tr("查看部件"))
        for label,key in (("整机","all"),("显卡","gpu"),("处理器","cpu"),("内存","memory"),("主板","board")):
            self.focus_choice.addItem(controller.tr(label),key)
        header.addWidget(self.focus_choice)
        reset=QPushButton(controller.tr("重置视角"));header.addWidget(reset)
        layout.addLayout(header)
        self.hint=QLabel(controller.tr("拖动旋转 · 滚轮缩放")+" · "+controller.tr("风扇按实际转速的 1/120 展示"))
        self.hint.setWordWrap(True);layout.addWidget(self.hint)
        self.viewport=viewport_factory(self);self.viewport.set_dark(dark)
        layout.addWidget(self.viewport,1)
        self.components=QLabel();self.components.setWordWrap(True);self.components.setTextFormat(Qt.PlainText)
        layout.addWidget(self.components)
        tools=QHBoxLayout()
        self.exploded=QCheckBox(controller.tr("展开组件"));tools.addWidget(self.exploded)
        self.animate=QCheckBox(controller.tr("风扇随转速转动"));tools.addWidget(self.animate)
        tools.addStretch(1)
        self.status=QLabel(controller.tr("比例示意 · 未知部件保留标记"));tools.addWidget(self.status)
        layout.addLayout(tools)
        self.exploded.toggled.connect(lambda value:controller.changeAssembly("exploded",value))
        self.animate.toggled.connect(lambda value:controller.changeAssembly("fan_animation",value))
        reset.clicked.connect(self.viewport.reset_camera)
        self.focus_choice.currentIndexChanged.connect(lambda _:self.viewport.focus_component(self.focus_choice.currentData()))
        self.viewport.rendererError.connect(self._render_failed)
        self.viewport.animationActiveChanged.connect(self._clock_active)
        self._clock_component=QQmlComponent(engine,QUrl.fromLocalFile(str(ASSETS/'native/AssemblyClock.qml')))
        self._clock=self._clock_component.createWithInitialProperties(dict(backend=self,active=False))
        if self._clock is None:raise RuntimeError("Assembly animation bridge could not load")
        self._clock.setParent(self)
        for signal,slot in ((controller.assemblyChanged,self._controller_changed),
                            (controller.dataChanged,self.update_readings),
                            (controller.motionChanged,self.update_readings)):
            signal.connect(slot);self._connections.append((signal,slot))
        self._viewer_active=True
        controller.set_assembly_viewer_active(True)
        self.synchronize(spec)

    def _controller_changed(self):
        spec=self.controller.assembly_specification()
        if spec:self.synchronize(spec)

    def synchronize(self,spec):
        if self._closing:return
        self._spec=copy.deepcopy(spec)
        geometry={key:spec[key] for key in ('case','gpu','cpu','memory','board')}
        signature=json.dumps(geometry,sort_keys=True,ensure_ascii=True)
        if signature!=self._geometry_key:
            baked=bake_profiles(spec,self.engine)
            self.viewport.set_scene(baked);self._geometry_key=signature
        options=spec['options']
        for control,field in ((self.exploded,'exploded'),(self.animate,'fan_animation')):
            control.blockSignals(True);control.setChecked(options[field]);control.blockSignals(False)
        self.viewport.set_exploded(options['exploded'])
        self.viewport.set_fan_animation_enabled(options['fan_animation'] and self.controller.motionEnabled and not self._renderer_error)
        self.title.setText(self.controller.tr(spec['case']['label']))
        self.components.setText(" · ".join((self.controller.tr(spec['cpu']['label']),self.controller.tr(spec['gpu']['label']),
            self.controller.tr("内存")+" "+str(spec['memory']['count'])+" "+self.controller.tr("条"))))
        self.update_readings()

    def update_readings(self):
        if self._closing:return
        self._last_fan=self.controller.assembly_fan_state()
        self.viewport.set_fan_state(self._last_fan.get('rpm'),self._last_fan.get('available') is True,
                                    self._last_fan.get('timestamp'))
        enabled=bool(self._spec and self._spec['options']['fan_animation'] and self.controller.motionEnabled
                     and not self._renderer_error)
        self.viewport.set_fan_animation_enabled(enabled)
        self._update_status()

    def _render_failed(self,_message):
        self._renderer_error=True
        self.viewport.set_fan_animation_enabled(False)
        self._clock_active(False)
        self._update_status()

    def _update_status(self):
        if self._renderer_error:
            text=self.controller.tr("当前环境无法显示三维视图")
        elif self._spec and self._spec['options']['fan_animation']:
            if not self.controller.motionEnabled:
                text=self.controller.tr("动效已关闭")
            elif self._last_fan.get('available') is True:
                text=self.controller.tr("显卡风扇")+" "+str(round(self._last_fan['rpm']))+" RPM"
            else:
                text=self.controller.tr("风扇转速不可用，保持静止")
        else:
            text=self.controller.tr("比例示意 · 未知部件保留标记")
        if self.status.text()!=text:self.status.setText(text)

    def _clock_active(self,active):
        if hasattr(self,'_clock') and self._clock is not None:
            self._clock.setProperty('active',active is True and not self._closing and not self._renderer_error)

    @Slot(float)
    def advanceFrame(self,elapsed):
        if self._closing:return
        timestamp=self._last_fan.get('timestamp')
        if (type(timestamp) not in (int,float) or not 0<=time.time()-timestamp<=GPU_FAN_MAX_AGE):
            self._last_fan=dict(available=False)
            self.viewport.set_fan_state(None,False);self._update_status();return
        self.viewport.advance_fans(elapsed)

    def showEvent(self,event):
        super().showEvent(event);self.update_readings()

    def changeEvent(self,event):
        super().changeEvent(event)
        if hasattr(self,'viewport'):self.update_readings()

    def _dispose(self):
        if self._closing:return
        self._closing=True
        self._clock_active(False)
        if self._clock is not None:
            self._clock.setProperty('backend',None);self._clock.deleteLater();self._clock=None
        if self._clock_component is not None:self._clock_component.deleteLater()
        if hasattr(self,'viewport'):self.viewport.close()
        for signal,slot in self._connections:signal.disconnect(slot)
        self._connections=[]
        if self._viewer_active:
            self._viewer_active=False
            self.controller.set_assembly_viewer_active(False)

    def closeEvent(self,event):
        self._dispose()
        self.closed.emit();event.accept()
