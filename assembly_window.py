"""Owned, on-demand 3D window; closed windows retain no graphics or clock."""
import copy
import json
import time

from PySide6.QtCore import Qt, Signal, Slot, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QCheckBox,QComboBox,QSizePolicy,QScrollArea,QFrame)

from assembly_profiles import bake_profiles
from assembly_config import HARDWARE_ICON_STYLES,detail_choices,style_choices
from assembly_inspection import COMPONENT_LABELS,snapshot as inspection_snapshot
from stats_config import ASSETS
from top_bar_feedback import GPU_FAN_MAX_AGE
from assembly_effects import component_family


class AssemblyWindow(QWidget):
    closed=Signal()
    window_mode='inspect'

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
        self._initialize_state()

        self.setAttribute(Qt.WA_DeleteOnClose,True)
        self.setWindowTitle(controller.tr("整机视图")+" · Desktop Stats")
        self.resize(1080,780);self.setMinimumSize(760,520)
        dark=controller.theme=="dark"
        self.setStyleSheet("QWidget{font-family:'Segoe UI','Microsoft YaHei UI';font-size:12px;color:"
            +("#e8edf2;background:#202731" if dark else "#293945;background:#f0f4f7")
            +";} QPushButton,QComboBox{padding:7px 12px;border:1px solid "
            +("#52606e" if dark else "#c8d2db")+";border-radius:6px;} QPushButton:hover{background:"
            +("#34404c" if dark else "#e2eaf0")+";}")
        self._build_inspector(controller,viewport_factory,dark)
        self._attach_session(controller,engine,spec)

    def _initialize_state(self):
        self._geometry_key=None;self._last_fan={};self._last_cpu_fan={};self._spec=None;self._renderer_error=False
        self._profile_key=None;self._profile_shapes=None
        self.selected_component='all';self.inspection_state=None;self._inspection_columns=0

    def _build_inspector(self,controller,viewport_factory,dark):
        layout=QVBoxLayout(self);layout.setContentsMargins(18,16,18,14);layout.setSpacing(8)
        header=QHBoxLayout();self.title=QLabel();self.title.setTextFormat(Qt.PlainText)
        self.title.setWordWrap(True);self.title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.title.setStyleSheet("font-size:19px;font-weight:600;")
        header.addWidget(self.title,1)
        self.focus_choice=QComboBox();self.focus_choice.setAccessibleName(controller.tr("查看部件"))
        for label,key in (("整机","all"),("显卡","gpu"),("处理器","cpu"),("内存","memory"),("主板","board"),("机箱","case")):
            self.focus_choice.addItem(controller.tr(label),key)
        for key in ('cooler','fans','psu','storage','expansion','cables'):
            self.focus_choice.addItem(controller.tr(COMPONENT_LABELS[key]),key)
        header.addWidget(self.focus_choice)
        reset=QPushButton(controller.tr("重置视角"));header.addWidget(reset)
        layout.addLayout(header)
        self.hint=QLabel(controller.tr("拖动旋转 · 滚轮缩放")+" · "+controller.tr("单击部件查看状态")
                        +" · "+controller.tr("风扇按实际转速的 1/120 展示"))
        self.hint.setWordWrap(True);layout.addWidget(self.hint)
        self.fit_notice=QLabel();self.fit_notice.setWordWrap(True);self.fit_notice.setTextFormat(Qt.PlainText)
        self.fit_notice.setStyleSheet('font-size:11px;color:'+('#edc57e' if dark else '#8a5922')+';')
        self.fit_notice.hide();layout.addWidget(self.fit_notice)
        style_row=QHBoxLayout();style_row.addWidget(QLabel(controller.tr("整机外观")))
        self.style_choice=QComboBox();self.style_choice.setAccessibleName(controller.tr("整机外观"))
        for row in style_choices(controller.tr):self.style_choice.addItem(row['label'],row['id'])
        style_row.addWidget(self.style_choice)
        self.preview_effect=QPushButton(controller.tr("预览特效"));self.preview_effect.setObjectName('previewAssemblyEffect')
        style_row.addWidget(self.preview_effect)
        self.selection_effects=QCheckBox(controller.tr("风格特效"));style_row.addWidget(self.selection_effects)
        style_row.addStretch(1);layout.addLayout(style_row)
        scene_row=QHBoxLayout();scene_row.setSpacing(16)
        self.viewport=viewport_factory(self);self.viewport.set_dark(dark)
        self.viewport.setMinimumHeight(240)
        scene_row.addWidget(self.viewport,1)
        inspector=QWidget();inspector.setObjectName('assemblyInspector')
        inspector.setFixedWidth(244)
        inspector_layout=QVBoxLayout(inspector);inspector_layout.setContentsMargins(0,0,0,0);inspector_layout.setSpacing(5)
        inspector_layout.setAlignment(Qt.AlignTop)
        inspector_header=QHBoxLayout()
        self.inspection_heading=QLabel(controller.tr("实时状态"));self.inspection_heading.setStyleSheet('font-weight:600;')
        self.inspection_heading.setWordWrap(True)
        inspector_header.addWidget(self.inspection_heading);inspector_header.addStretch(1)
        self.component_choice=QComboBox();self.component_choice.setObjectName('assemblyComponentChoice')
        self.component_choice.setMaximumWidth(130)
        self.component_choice.setAccessibleName(controller.tr("选中部件"))
        for key,label in COMPONENT_LABELS.items():self.component_choice.addItem(controller.tr(label),key)
        inspector_header.addWidget(self.component_choice);inspector_layout.addLayout(inspector_header)
        self.components=QLabel();self.components.setWordWrap(True);self.components.setTextFormat(Qt.PlainText)
        self.components.setObjectName('assemblySelectedIdentity');inspector_layout.addWidget(self.components)
        self._inspection_grid=QGridLayout();self._inspection_grid.setContentsMargins(0,0,0,0)
        self._inspection_grid.setHorizontalSpacing(18);self._inspection_grid.setVerticalSpacing(3)
        self.inspection_rows=[]
        for index in range(6):
            cell=QWidget();cell.setMinimumWidth(0)
            cell_layout=QHBoxLayout(cell);cell_layout.setContentsMargins(0,0,0,0);cell_layout.setSpacing(8)
            label=QLabel();label.setWordWrap(True);label.setTextFormat(Qt.PlainText)
            label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
            value=QLabel('—');value.setTextFormat(Qt.PlainText);value.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
            value.setWordWrap(False);value.setMaximumWidth(150)
            value.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Preferred)
            value.setObjectName('assemblyReading'+str(index));value.setStyleSheet('font-weight:600;font-size:13px;')
            cell_layout.addWidget(label,1);cell_layout.addWidget(value)
            self.inspection_rows.append((cell,label,value))
        inspector_layout.addLayout(self._inspection_grid)
        self.inspection_note=QLabel();self.inspection_note.setTextFormat(Qt.PlainText);self.inspection_note.setWordWrap(True)
        self.inspection_note.setStyleSheet('font-size:11px;');inspector_layout.addWidget(self.inspection_note)
        detail_row=QHBoxLayout();detail_label=QLabel(controller.tr('模型细节'));detail_label.setWordWrap(True)
        detail_label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);detail_row.addWidget(detail_label,1)
        self.detail_choice=QComboBox();self.detail_choice.setObjectName('assemblyDetailChoice');self.detail_choice.setFixedWidth(140)
        self.detail_choice.setAccessibleName(controller.tr('模型细节'))
        for row in detail_choices(controller.tr):self.detail_choice.addItem(row['label'],row['id'])
        detail_row.addWidget(self.detail_choice);inspector_layout.addLayout(detail_row)
        self.part_style_choice=QComboBox();self.part_style_choice.setObjectName('assemblyPartStyleChoice')
        for row in style_choices(controller.tr):
            self.part_style_choice.addItem(controller.tr('跟随默认外观') if row['id']=='follow' else row['label'],row['id'])
        self.part_style_choice.setAccessibleName(controller.tr('此部件外观'))
        inspector_layout.addWidget(QLabel(controller.tr('此部件外观')));inspector_layout.addWidget(self.part_style_choice)
        self.reference_choice=QComboBox();self.reference_choice.setObjectName('assemblyReferenceChoice')
        for label,key in (("载入参考装机",""),("风冷参考装机","air"),("一体水冷参考装机","aio"),("分体水冷参考装机","loop")):
            self.reference_choice.addItem(controller.tr(label),key)
        self.reference_choice.setAccessibleName(controller.tr('载入参考装机'))
        inspector_layout.addWidget(self.reference_choice)
        inspector_scroll=QScrollArea();inspector_scroll.setObjectName('assemblyInspectorScroll')
        inspector_scroll.setWidgetResizable(True);inspector_scroll.setFrameShape(QFrame.NoFrame)
        inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);inspector_scroll.setFixedWidth(262)
        inspector_scroll.setWidget(inspector);scene_row.addWidget(inspector_scroll);layout.addLayout(scene_row,1)
        tools=QHBoxLayout()
        self.exploded=QCheckBox(controller.tr("展开组件"));tools.addWidget(self.exploded)
        self.animate=QCheckBox(controller.tr("风扇随转速转动"));tools.addWidget(self.animate)
        tools.addStretch(1)
        self.status=QLabel(controller.tr("比例示意 · 未知部件保留标记"));tools.addWidget(self.status)
        self.status.setWordWrap(True);self.status.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        layout.addLayout(tools)
        self.exploded.toggled.connect(lambda value:controller.changeAssembly("exploded",value))
        self.animate.toggled.connect(lambda value:controller.changeAssembly("fan_animation",value))
        self.style_choice.currentIndexChanged.connect(
            lambda _:controller.changeAssembly("appearance_style",self.style_choice.currentData()))
        self.selection_effects.toggled.connect(lambda value:controller.changeAssembly('selection_effects',value))
        self.detail_choice.currentIndexChanged.connect(lambda _:controller.changeAssembly('detail_level',self.detail_choice.currentData()))
        self.reference_choice.activated.connect(self._load_reference)
        self.part_style_choice.activated.connect(lambda _:controller.changeAssemblyPartStyle(
            self.selected_component,self.part_style_choice.currentData()) if self.selected_component!='all' else None)
        self.preview_effect.clicked.connect(lambda:self.viewport.preview_effect(
            self.focus_choice.currentData() if self.focus_choice.currentData()!='all'
            else self.selected_component if self.selected_component!='all' else 'case'))
        self.component_choice.currentIndexChanged.connect(self._choose_component)
        self.viewport.componentSelected.connect(self._component_selected)
        reset.clicked.connect(self.viewport.reset_camera)
        self.focus_choice.currentIndexChanged.connect(lambda _:self.viewport.focus_component(self.focus_choice.currentData()))
        self.viewport.rendererError.connect(self._render_failed)
        self.viewport.animationActiveChanged.connect(self._clock_active)

    def _attach_session(self,controller,engine,spec):
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
        if not self._apply_scene(spec):return
        options=spec['options']
        detail=spec.get('detail_level','balanced')
        if detail not in ('eco','balanced','close'):detail='balanced'
        self.detail_choice.blockSignals(True);self.detail_choice.setCurrentIndex(self.detail_choice.findData(detail))
        self.detail_choice.blockSignals(False)
        self.style_choice.blockSignals(True)
        self.style_choice.setCurrentIndex(self.style_choice.findData(options.get('appearance_style','follow')))
        self.style_choice.blockSignals(False)
        for control,field in ((self.exploded,'exploded'),(self.animate,'fan_animation')):
            control.blockSignals(True);control.setChecked(options[field]);control.blockSignals(False)
        self.selection_effects.blockSignals(True);self.selection_effects.setChecked(options.get('selection_effects',True))
        self.selection_effects.blockSignals(False)
        self._sync_part_style()
        self._apply_motion_options(options)
        self.title.setText(self.controller.tr(spec['case']['label']))
        self.update_readings()

    def _apply_scene(self,spec):
        """Shared bounded scene/profile cache, independent of window chrome."""
        if self._closing:return False
        previous_spec=self._spec
        self._spec=copy.deepcopy(spec)
        geometry={key:spec[key] for key in ('case','gpu','cpu','memory','board')}
        geometry.update(cooling=spec.get('cooling',{}),auxiliary=spec.get('auxiliary',{}))
        geometry['part_styles']=spec.get('part_styles',{})
        geometry['lighting_preview']=spec.get('lighting_preview','artwork')
        geometry['model_library_generation']=spec.get('model_library_generation',0)
        resolved=spec.get('visual_style','miniature')
        if resolved not in HARDWARE_ICON_STYLES:resolved='miniature'
        geometry['visual_style']=resolved
        detail=spec.get('detail_level','balanced')
        if detail not in ('eco','balanced','close'):detail='balanced'
        geometry['detail_level']=detail
        signature=json.dumps(geometry,sort_keys=True,ensure_ascii=True)
        if signature!=self._geometry_key:
            profile_key=json.dumps({key:spec[key] for key in ('gpu','cpu','memory')},sort_keys=True,ensure_ascii=True)
            if profile_key!=self._profile_key:
                baked=bake_profiles(spec,self.engine)
                self._profile_shapes={key:baked[key] for key in ('gpu','cpu','memory')}
                self._profile_key=profile_key
            else:baked=dict(spec,**copy.deepcopy(self._profile_shapes))
            baked['visual_style']=resolved
            baked['detail_level']=detail
            try:self.viewport.set_scene(baked)
            except ValueError:
                self._spec=previous_spec
                self.fit_notice.setText(self.controller.tr('暂未应用本次视图更改，请减少配件或调整模型细节。'))
                self.fit_notice.setVisible(True)
                return False
            self._geometry_key=signature
            self._refresh_part_choices()
            from assembly_parts import fit_messages
            notes=fit_messages(spec,getattr(getattr(self.viewport,'scene',None),'metadata',{}))
            self.fit_notice.setText(' · '.join(self.controller.tr(note) for note in notes))
            self.fit_notice.setVisible(bool(notes))
        return True

    def _apply_motion_options(self,options):
        self.viewport.set_selection_effects_enabled(options.get('selection_effects',True))
        self.viewport.set_exploded(options['exploded'])
        if hasattr(self.viewport,'set_inspection_cutaway'):self.viewport.set_inspection_cutaway(options.get('inspection_cutaway',False))
        if hasattr(self.viewport,'set_fan_motion'):self.viewport.set_fan_motion(options.get('fan_motion','measured'))
        self.viewport.set_fan_animation_enabled(options['fan_animation'] and self.controller.motionEnabled
            and self.property('modelMotionAllowed') is not False and not self._renderer_error)

    def update_readings(self):
        if self._closing or not self.isVisible() or self.isMinimized():return
        self._last_fan=self.controller.assembly_fan_state()
        from assembly_feedback import cpu_fan_state
        self._last_cpu_fan=(self.controller.assembly_cpu_fan_state() if hasattr(self.controller,'assembly_cpu_fan_state')
                            else cpu_fan_state(getattr(self.controller,'readings',{})))
        # A rejected draft may differ from the model still on screen. Gate
        # against the applied scene as well as the controller's current draft.
        if self._spec and self._spec.get('gpu',{}).get('telemetry_bound') is False:
            self._last_fan=dict(available=False,rpm=None)
        if self._spec and self._spec.get('cpu',{}).get('telemetry_bound') is False:
            self._last_cpu_fan=dict(available=False,rpm=None)
        motion=self.controller.motionEnabled and self.property('modelMotionAllowed') is not False and not self._renderer_error
        self.viewport.set_motion_enabled(motion)
        self.viewport.set_fan_state(self._last_fan.get('rpm'),self._last_fan.get('available') is True,
                                    self._last_fan.get('timestamp'))
        if hasattr(self.viewport,'set_cpu_fan_state'):
            self.viewport.set_cpu_fan_state(self._last_cpu_fan.get('rpm'),self._last_cpu_fan.get('available') is True,
                                           self._last_cpu_fan.get('timestamp'))
        enabled=bool(self._spec and self._spec['options']['fan_animation'] and self.controller.motionEnabled
                     and self.property('modelMotionAllowed') is not False and not self._renderer_error)
        self.viewport.set_fan_animation_enabled(enabled)
        if hasattr(self,'preview_effect'):
            self.preview_effect.setEnabled(motion and bool(self._spec and self._spec['options'].get('selection_effects',True)))
        self._update_status()
        self._update_inspection()

    def _choose_component(self,_index):
        self._component_selected(self.component_choice.currentData())
        self.viewport.select_component(self.selected_component)

    def _component_selected(self,name):
        if self._closing:return
        name=name if component_family(name) in COMPONENT_LABELS else 'all'
        changed=name!=self.selected_component
        self.selected_component=name
        self.component_choice.blockSignals(True)
        self.component_choice.setCurrentIndex(self.component_choice.findData(name))
        self.component_choice.blockSignals(False)
        if changed or self.inspection_state is None:self._update_inspection()
        self._sync_part_style()

    def _sync_part_style(self):
        if not self._spec:return
        self.part_style_choice.blockSignals(True)
        selected=self._spec.get('part_styles',{}).get(self.selected_component,'follow')
        self.part_style_choice.setCurrentIndex(self.part_style_choice.findData(selected))
        self.part_style_choice.setEnabled(self.selected_component!='all')
        self.part_style_choice.blockSignals(False)

    def _update_inspection(self):
        if self._closing or not self._spec or not self.isVisible() or self.isMinimized():return
        state=inspection_snapshot(getattr(self.controller,'readings',{}),self._spec,
                                  getattr(self.controller,'draft',{}),self.selected_component,
                                  scene_metadata=getattr(getattr(self.viewport,'scene',None),'metadata',{}))
        if state==self.inspection_state:return
        self.inspection_state=state
        self.components.setText(' · '.join(self.controller.tr(part) for part in state['identity_parts']))
        columns=1
        if columns!=self._inspection_columns:
            self._inspection_columns=columns
            for index,(cell,_label,_value) in enumerate(self.inspection_rows):
                self._inspection_grid.addWidget(cell,index//columns,index%columns)
            for index in range(3):self._inspection_grid.setColumnStretch(index,1 if index<columns else 0)
        for index,(cell,label,value) in enumerate(self.inspection_rows):
            active=index<len(state['rows']);cell.setVisible(active)
            if not active:continue
            row=state['rows'][index]
            label.setText(self.controller.tr(row['label']));value.setText(self.controller.tr(row['value']))
            tip=' · '.join(part for part in (self.controller.tr(row.get('reason','')),row.get('source','')) if part)
            cell.setToolTip(tip)
        self.inspection_note.setText(' · '.join(self.controller.tr(note) for note in state['notes']))
        self.inspection_note.setVisible(bool(state['notes']))

    def _render_failed(self,_message):
        self._renderer_error=True
        self.viewport.set_fan_animation_enabled(False)
        self.viewport.set_motion_enabled(False)
        self._clock_active(False)
        self._update_status()

    def _update_status(self):
        if self._renderer_error:
            text=self.controller.tr("当前环境无法显示三维视图")
        elif self._spec and self._spec['options']['fan_animation']:
            if not self.controller.motionEnabled:
                text=self.controller.tr("动效已关闭")
            elif self._spec['options'].get('fan_motion')=='demo':
                text=self.controller.tr('参考转动（非实测）')+' · 1200 RPM / 120'
            elif component_family(self.selected_component)=='cooler' and self._last_cpu_fan.get('available') is True:
                text='CPU_FAN '+str(round(self._last_cpu_fan['rpm']))+' RPM · '+self.controller.tr('代表通道')
            elif self._last_fan.get('available') is True:
                text=self.controller.tr("显卡风扇")+" "+str(round(self._last_fan['rpm']))+" RPM"
            else:
                text=self.controller.tr("风扇转速不可用，保持静止")
        else:
            text=self.controller.tr("比例示意 · 未知部件保留标记")
        if self.status.text()!=text:self.status.setText(text)

    def _load_reference(self,index):
        kind=self.reference_choice.itemData(index)
        if kind and hasattr(self.controller,'useAssemblyReference'):self.controller.useAssemblyReference(kind)
        self.reference_choice.setCurrentIndex(0)

    def _refresh_part_choices(self):
        metadata=getattr(getattr(self.viewport,'scene',None),'metadata',{})
        parts=[]
        for group in ('hardware','cooling','auxiliary'):
            parts.extend(row for row in metadata.get(group,{}).get('parts',())
                         if isinstance(row,dict) and row.get('id') and row.get('label'))
        for choice in (self.component_choice,self.focus_choice):
            selected=choice.currentData() or 'all';choice.blockSignals(True);choice.clear()
            for key,label in COMPONENT_LABELS.items():choice.addItem(self.controller.tr(label),key)
            if parts:choice.insertSeparator(choice.count())
            for row in parts:choice.addItem(row['label'],row['id'])
            index=choice.findData(selected);choice.setCurrentIndex(index if index>=0 else 0)
            choice.blockSignals(False)

    def _clock_active(self,active):
        if hasattr(self,'_clock') and self._clock is not None:
            self._clock.setProperty('active',active is True and not self._closing and not self._renderer_error
                                    and self.property('modelMotionAllowed') is not False
                                    and self.isVisible() and not self.isMinimized())

    @Slot(float)
    def advanceFrame(self,elapsed):
        if self._closing:return
        timestamp=self._last_fan.get('timestamp')
        if (type(timestamp) not in (int,float) or not 0<=time.time()-timestamp<=GPU_FAN_MAX_AGE) and self._last_fan.get('available') is True:
            self._last_fan=dict(available=False)
            self.viewport.set_fan_state(None,False);self._update_status();self._update_inspection()
        cpu_stamp=self._last_cpu_fan.get('timestamp')
        if (type(cpu_stamp) not in (int,float) or not 0<=time.time()-cpu_stamp<=GPU_FAN_MAX_AGE) and self._last_cpu_fan.get('available') is True:
            self._last_cpu_fan=dict(available=False)
            if hasattr(self.viewport,'set_cpu_fan_state'):self.viewport.set_cpu_fan_state(None,False)
            self._update_status();self._update_inspection()
        self.viewport.advance_animations(elapsed)

    def showEvent(self,event):
        super().showEvent(event);self.update_readings()

    def hideEvent(self,event):
        self._clock_active(False)
        super().hideEvent(event)

    def changeEvent(self,event):
        super().changeEvent(event)
        if hasattr(self,'viewport'):
            if hasattr(self.viewport,'refresh_visibility'):self.viewport.refresh_visibility()
            if self.isMinimized():self._clock_active(False)
            self.update_readings()

    def _dispose(self):
        if self._closing:return
        self._closing=True
        self._profile_shapes=None;self._profile_key=None
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


def create_assembly_window(controller,engine,spec,*,viewport_factory=None):
    """Lazy factory. Caller owns screen/fullscreen checks and showing the window."""
    if spec.get('options',{}).get('window_mode')=='desktop':
        from assembly_desktop_widget import AssemblyWidgetWindow
        return AssemblyWidgetWindow(controller,engine,spec,viewport_factory=viewport_factory)
    return AssemblyWindow(controller,engine,spec,viewport_factory=viewport_factory)
