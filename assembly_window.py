"""Owned, on-demand 3D window; closed windows retain no graphics or clock."""
import copy
import json
import time

from PySide6.QtCore import Qt, Signal, Slot, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QCheckBox,QComboBox,QSizePolicy,QScrollArea,QFrame)

from assembly_profiles import bake_profiles
from assembly_config import HARDWARE_ICON_STYLES,detail_choices,style_choices
from assembly_inspection import COMPONENT_LABELS,part_family,snapshot as inspection_snapshot
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
        self.gpu_assembly_heading=QLabel(controller.tr('显卡插拔演示'));inspector_layout.addWidget(self.gpu_assembly_heading)
        gpu_controls=QHBoxLayout()
        self.gpu_remove=QPushButton(controller.tr('拔出查看'));self.gpu_remove.setObjectName('assemblyGpuRemove')
        self.gpu_insert=QPushButton(controller.tr('插回插槽'));self.gpu_insert.setObjectName('assemblyGpuInsert')
        gpu_controls.addWidget(self.gpu_remove);gpu_controls.addWidget(self.gpu_insert)
        inspector_layout.addLayout(gpu_controls)
        self.gpu_assembly_hint=QLabel();self.gpu_assembly_hint.setWordWrap(True);self.gpu_assembly_hint.setTextFormat(Qt.PlainText)
        self.gpu_assembly_hint.setStyleSheet('font-size:11px;');inspector_layout.addWidget(self.gpu_assembly_hint)
        self.gpu_remove.clicked.connect(lambda:self._preview_gpu_insertion(True))
        self.gpu_insert.clicked.connect(lambda:self._preview_gpu_insertion(False))
        self.part_assembly_heading=QLabel(controller.tr('部件插拔'));inspector_layout.addWidget(self.part_assembly_heading)
        part_controls=QHBoxLayout()
        self.part_remove=QPushButton(controller.tr('取出查看'));self.part_remove.setObjectName('assemblyPartRemove')
        self.part_insert=QPushButton(controller.tr('插回原位'));self.part_insert.setObjectName('assemblyPartInsert')
        part_controls.addWidget(self.part_remove);part_controls.addWidget(self.part_insert);inspector_layout.addLayout(part_controls)
        self.part_retention=QCheckBox(controller.tr('暂时隐藏固定扣具'));self.part_retention.setObjectName('assemblyPartRetentionHidden')
        self.part_retention.setToolTip(controller.tr('仅用于检视；尚未模拟锁扣、螺丝的开合。'));inspector_layout.addWidget(self.part_retention)
        self.part_mount_release=QCheckBox(controller.tr('参考解除安装固定与连接'));self.part_mount_release.setObjectName('assemblyPartMountReleased')
        self.part_mount_release.setToolTip(controller.tr('仅在当前检视中确认手动解除固定并隐藏已核连接线；没有模拟真实螺丝和插头操作。'))
        inspector_layout.addWidget(self.part_mount_release)
        self.part_assembly_hint=QLabel();self.part_assembly_hint.setWordWrap(True);self.part_assembly_hint.setTextFormat(Qt.PlainText)
        self.part_assembly_hint.setStyleSheet('font-size:11px;');inspector_layout.addWidget(self.part_assembly_hint)
        visibility_row=QHBoxLayout()
        self.part_hidden=QCheckBox(controller.tr('暂时隐藏此部件'));self.part_hidden.setObjectName('assemblyPartHidden')
        self.part_hidden.setToolTip(controller.tr('只改变当前检视，不删除模型，也不改变硬件监控。'))
        self.restore_hidden=QPushButton(controller.tr('全部显示'));self.restore_hidden.setObjectName('assemblyRestoreHidden')
        visibility_row.addWidget(self.part_hidden);visibility_row.addWidget(self.restore_hidden);inspector_layout.addLayout(visibility_row)
        self.part_remove.clicked.connect(lambda:self._preview_part_motion(True))
        self.part_insert.clicked.connect(lambda:self._preview_part_motion(False))
        self.part_retention.toggled.connect(self._toggle_retention)
        self.part_mount_release.toggled.connect(self._toggle_mount_release)
        self.part_hidden.toggled.connect(self._toggle_part_hidden)
        self.restore_hidden.clicked.connect(self._restore_hidden)
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
        self.show_psu=QCheckBox(controller.tr('展示电源'));self.show_psu.setObjectName('assemblyShowPsuCheck')
        self.show_psu.setToolTip(controller.tr('有电源仓时临时移开遮罩；开放式机箱仍按实际布局显示。'));tools.addWidget(self.show_psu)
        self.animate=QCheckBox(controller.tr("风扇随转速转动"));tools.addWidget(self.animate)
        tools.addStretch(1)
        self.status=QLabel(controller.tr("比例示意 · 未知部件保留标记"));tools.addWidget(self.status)
        self.status.setWordWrap(True);self.status.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        layout.addLayout(tools)
        self.exploded.toggled.connect(lambda value:controller.changeAssembly("exploded",value))
        self.show_psu.toggled.connect(lambda value:controller.changeAssembly('show_psu',value))
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
        self.focus_choice.currentIndexChanged.connect(self._focus_view)
        self.viewport.rendererError.connect(self._render_failed)
        self.viewport.animationActiveChanged.connect(self._clock_active)

    def _attach_session(self,controller,engine,spec):
        self._clock_component=QQmlComponent(engine,QUrl.fromLocalFile(str(ASSETS/'native/AssemblyClock.qml')))
        self._clock=self._clock_component.createWithInitialProperties(dict(backend=self,active=False))
        if self._clock is None:raise RuntimeError("Assembly animation bridge could not load")
        self._clock.setParent(self)
        gpu_signal=getattr(self.viewport,'gpuAssemblyChanged',None)
        if gpu_signal is not None:
            gpu_signal.connect(self._sync_gpu_assembly);self._connections.append((gpu_signal,self._sync_gpu_assembly))
        part_signal=getattr(self.viewport,'partAssemblyChanged',None)
        if part_signal is not None:
            part_signal.connect(self._sync_part_assembly);self._connections.append((part_signal,self._sync_part_assembly))
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
        for control,field in ((self.exploded,'exploded'),(self.show_psu,'show_psu'),(self.animate,'fan_animation')):
            control.blockSignals(True);control.setChecked(options.get(field,False));control.blockSignals(False)
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
        if hasattr(self.viewport,'set_show_psu'):self.viewport.set_show_psu(options.get('show_psu',False))
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
        self._sync_gpu_assembly()
        self._sync_part_assembly()

    def _gpu_assembly_state(self):
        method=getattr(self.viewport,'gpu_insertion_state',None)
        state=method() if callable(method) else dict(available=False,reason='scene_unavailable',active=False,progress=0.)
        if (self._renderer_error or not self.controller.motionEnabled or self.property('modelMotionAllowed') is False):
            state=dict(state,available=False,reason='动效已关闭。')
        return state

    def _part_family(self,name=None):
        scene=getattr(self.viewport,'scene',None)
        return part_family(self.selected_component if name is None else name,
                           getattr(scene,'metadata',None))

    def _gpu_assembly_reason(self,state):
        reasons={
            'scene_unavailable':'当前模型尚未准备好。',
            'gpu_mount_unsupported':'此安装方式尚未支持显卡插拔演示。',
            'gpu_waterblock_unsupported':'水冷显卡的管路拆装尚未支持。',
            'board_normal_unverified':'尚未确认此模型的插槽方向。',
            'case_dimensions_unverified':'尚未确认此机箱的内部范围。',
            'gpu_geometry_unverified':'当前显卡模型尚未准备好。',
            'gpu_outside_case_envelope':'此显卡超出机箱参考范围，暂不演示插拔。',
            'insufficient_side_clearance':'此机箱的侧向空间不足以演示脱离插槽。',
            'gpu_cable_metadata_invalid':'此模型的显卡供电线关联尚未准备好。',
            'gpu_cable_prefix_missing':'此模型的显卡供电线关联尚未准备好。',
            'gpu_cable_geometry_unverified':'此模型的显卡供电线关联尚未准备好。',
            'gpu_cable_prefix_ambiguous':'此模型的显卡供电线关联尚未准备好。',
            'cable_owner_unverified':'此模型的显卡供电线关联尚未准备好。',
            '请先关闭展开组件，再演示显卡插拔。':'请先关闭展开组件，再演示显卡插拔。',
            '请先切换到整机或显卡视图。':'请先切换到整机或显卡视图。',
            '动效已关闭。':'动效已关闭。',
            'return_other_part_first':'请先把当前部件插回原位。',
            'target_hidden':'部件已暂时隐藏，请先恢复显示。',
        }
        return self.controller.tr(reasons.get(state.get('reason'),'当前模型尚未准备好。'))

    def _sync_gpu_assembly(self):
        if self._closing:return
        state=self._gpu_assembly_state();enabled=state.get('available') is True and not state.get('active')
        if hasattr(self,'gpu_remove'):
            visible=self._part_family() in ('all','gpu')
            for control in (self.gpu_assembly_heading,self.gpu_remove,self.gpu_insert,self.gpu_assembly_hint):control.setVisible(visible)
            self.gpu_remove.setEnabled(enabled and state.get('progress',0.)<1.)
            self.gpu_insert.setEnabled(enabled and state.get('progress',0.)>0.)
            note=(self.controller.tr('沿插槽方向移动；未模拟螺丝、卡扣及电源线拔插。')
                  if state.get('available') else self._gpu_assembly_reason(state))
            if self.gpu_assembly_hint.text()!=note:self.gpu_assembly_hint.setText(note)
        if hasattr(self,'status'):self._update_status()

    def _preview_gpu_insertion(self,removed):
        if not self._can_interact():return False
        if not self._gpu_assembly_state().get('available'):
            self._sync_gpu_assembly();return False
        method=getattr(self.viewport,'preview_gpu_insertion',None)
        accepted=bool(callable(method) and method(removed))
        self._sync_gpu_assembly();return accepted

    def _part_assembly_state(self):
        method=getattr(self.viewport,'part_motion_state',None)
        state=method() if callable(method) else dict(available=False,reason='choose_cpu_or_memory',active=False,progress=0.,hidden_parts=())
        if self._renderer_error or not self.controller.motionEnabled or self.property('modelMotionAllowed') is False:
            state=dict(state,available=False,reason='motion_disabled')
        return state

    def _part_assembly_reason(self,state):
        labels={
            'choose_cpu_or_memory':'选择处理器、单条内存或机箱风扇，查看装配方向。',
            'choose_individual_case_fan':'请先选择一把机箱风扇。',
            'case_fan_release_required':'请先确认参考解除这把风扇的安装固定与已核连接。',
            'case_fan_mount_unverified':'尚未确认此风扇的安装面，暂不演示移动。',
            'mount_plane_frame_missing':'此机箱缺少已记录的安装面信息，暂不演示移动。',
            'fan_connections_unverified':'这把风扇的连接线尚未确认，暂不演示移动。',
            'radiator_fan_internal_harness_unverified':'冷排风扇的内部线束尚未确认，暂不单独移动。',
            'choose_individual_part':'请先选择一条内存。',
            'target_hidden':'部件已暂时隐藏，请先恢复显示。',
            'cooler_must_be_hidden_or_moved_first':'散热器挡住处理器，请先在检视中暂时隐藏散热器。',
            'motion_path_blocked':'移动路线被其他部件挡住，请先检查或暂时隐藏遮挡部件。',
            'open_retention_first':'请先在检视中隐藏固定扣具。',
            'close_exploded_view':'请先关闭展开组件。',
            'motion_disabled':'动效已关闭。',
            'return_other_part_first':'请先把当前部件插回原位。',
            'focus_selected_part':'请切换到整机或当前部件视图。',
            'insufficient_case_clearance':'机箱内部空间不足，暂不演示这条移动路线。',
            'sodimm_release_orientation_unverified':'尚未核实此内存插槽的开启角度。',
            'clearance_budget_exceeded':'此组合的移动空间尚未确认，暂不演示。',
            'connection_ownership_unverified':'尚未确认此部件的连接线，暂不演示。',
        }
        return self.controller.tr(labels.get(state.get('reason'),'此部件的装配方向尚未确认。'))

    def _sync_part_assembly(self):
        if self._closing:return
        state=self._part_assembly_state();kind=self._part_family()
        if hasattr(self,'part_remove'):
            visible=kind in ('cpu','memory','fans')
            for control in (self.part_assembly_heading,self.part_remove,self.part_insert,self.part_retention,self.part_assembly_hint):control.setVisible(visible)
            self.part_retention.setVisible(visible and kind!='fans')
            self.part_mount_release.setVisible(visible and kind=='fans')
            allowed=state.get('allowed_mount_release_part_ids',())
            released=self.selected_component in state.get('released_mounts',())
            self.part_mount_release.blockSignals(True);self.part_mount_release.setChecked(released);self.part_mount_release.blockSignals(False)
            self.part_mount_release.setEnabled(self.selected_component in allowed and not state.get('active')
                and state.get('reason') not in ('motion_disabled','return_other_part_first','close_exploded_view'))
            enabled=state.get('available') is True and not state.get('active')
            self.part_remove.setEnabled(enabled and state.get('progress',0.)<1.)
            self.part_insert.setEnabled(enabled and state.get('progress',0.)>0.)
            self.part_retention.blockSignals(True);self.part_retention.setChecked(state.get('retention_hidden') is True);self.part_retention.blockSignals(False)
            self.part_retention.setEnabled(bool(state.get('allowed_opened_mesh_names')) and not state.get('active'))
            hidden=state.get('hidden_parts',())
            self.part_hidden.blockSignals(True);self.part_hidden.setChecked(self.selected_component in hidden);self.part_hidden.blockSignals(False)
            self.part_hidden.setEnabled(self.selected_component!='all' and callable(getattr(self.viewport,'set_part_hidden',None)))
            self.restore_hidden.setEnabled(bool(hidden) or state.get('retention_hidden') is True or bool(state.get('released_mounts')))
            if state.get('available'):
                distance=state.get('distance_mm')
                note=self.controller.tr('仅向机箱内侧脱离安装面；固定与接线仅为参考解除，不代表完整出箱。'
                    if kind=='fans' else '仅沿插槽方向分离；未模拟锁扣和螺丝，不代表完整出箱。')
                if type(distance) in (int,float):note+=f' {distance:.1f} mm'
            else:note=self._part_assembly_reason(state)
            if self.part_assembly_hint.text()!=note:self.part_assembly_hint.setText(note)
        if hasattr(self,'status'):self._update_status()

    def _preview_part_motion(self,removed):
        if not self._can_interact() or not self._part_assembly_state().get('available'):return False
        method=getattr(self.viewport,'preview_part_motion',None)
        result=bool(callable(method) and method(removed));self._sync_part_assembly();return result

    def _toggle_part_hidden(self,enabled):
        method=getattr(self.viewport,'set_part_hidden',None)
        result=bool(self._can_interact() and callable(method) and method(self.selected_component,enabled))
        self._sync_part_assembly();self._sync_gpu_assembly();return result

    def _restore_hidden(self):
        method=getattr(self.viewport,'restore_hidden_parts',None)
        result=bool(self._can_interact() and callable(method) and method())
        self._sync_part_assembly();self._sync_gpu_assembly();return result

    def _toggle_retention(self,enabled):
        method=getattr(self.viewport,'set_retention_hidden',None)
        result=bool(self._can_interact() and callable(method) and method(enabled))
        self._sync_part_assembly();return result

    def _toggle_mount_release(self,enabled):
        method=getattr(self.viewport,'set_mount_released',None)
        result=bool(self._can_interact() and callable(method) and method(enabled))
        self._sync_part_assembly();return result

    def _focus_view(self,_index):
        selected=self.focus_choice.currentData();self.viewport.focus_component(selected)
        if selected!='all':
            self._component_selected(selected);self.viewport.select_component(selected)
        self._sync_gpu_assembly();self._sync_part_assembly()

    def _choose_component(self,_index):
        self._component_selected(self.component_choice.currentData())
        self.viewport.select_component(self.selected_component)

    def _component_selected(self,name):
        if self._closing:return
        name=name if name=='all' or self._part_family(name)!='all' else 'all'
        changed=name!=self.selected_component
        self.selected_component=name
        self.component_choice.blockSignals(True)
        self.component_choice.setCurrentIndex(self.component_choice.findData(name))
        self.component_choice.blockSignals(False)
        if changed or self.inspection_state is None:self._update_inspection()
        self._sync_part_style()
        self._sync_gpu_assembly();self._sync_part_assembly()

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
        gpu=self._gpu_assembly_state()
        part=self._part_assembly_state()
        if self._renderer_error:
            text=self.controller.tr("当前环境无法显示三维视图")
        elif part.get('active'):
            text=self.controller.tr('部件正在取出（参考）' if part.get('motion_target')==1. else '部件正在插回（参考）')
        elif part.get('progress',0.)>0:
            text=self.controller.tr('部件已与安装面分离（参考）；实际监控继续。'
                if part.get('kind')=='case_fan' else '部件已与插槽分离（参考）；实际监控继续。')
        elif gpu.get('active'):
            text=self.controller.tr('模型正在脱离插槽（演示）' if gpu.get('target')==1. else '模型正在插回插槽（演示）')
        elif gpu.get('progress',0.)>0:
            text=self.controller.tr('模型已脱离插槽（演示）；实际监控继续。')
        elif self._spec and self._spec['options']['fan_animation']:
            if not self.controller.motionEnabled:
                text=self.controller.tr("动效已关闭")
            elif self._spec['options'].get('fan_motion')=='demo':
                text=self.controller.tr('参考转动（非实测）')+' · 1200 RPM / 120'
            elif self._part_family()=='cooler' and self._last_cpu_fan.get('available') is True:
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

    def _can_interact(self):
        return (not self._closing and self.isVisible() and not self.isMinimized()
                and self.property('modelMotionAllowed') is not False)

    def _close_owned_popups(self):
        # Qt popups are separate top-level surfaces: hiding/minimizing their
        # owner does not reliably hide them. Close only this window's known
        # menus/choices, without enumerating desktop windows or polling.
        menu=getattr(self,'_context_menu',None)
        if menu is not None:menu.close()
        for name in ('focus_choice','component_choice','style_choice','detail_choice','part_style_choice','reference_choice'):
            control=getattr(self,name,None)
            if isinstance(control,QComboBox):control.hidePopup()

    def hideEvent(self,event):
        self._close_owned_popups()
        self._clock_active(False)
        super().hideEvent(event)

    def changeEvent(self,event):
        super().changeEvent(event)
        if hasattr(self,'viewport'):
            if hasattr(self.viewport,'refresh_visibility'):self.viewport.refresh_visibility()
            if self.isMinimized():self._close_owned_popups();self._clock_active(False)
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
