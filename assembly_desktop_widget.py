"""Compact desktop assembly presentation; owns no sampler or animation timer.

Uses the inspector's scene/profile cache, reading snapshot and one AssemblyClock.
Windows transparency is alpha composition, never color-key substitution. Actual
Windows desktop composition is an explicit later acceptance step, not inferred
from offscreen tests.
"""
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QTextLayout, QTextOption
from PySide6.QtWidgets import (QHBoxLayout,QLabel,QMenu,QPushButton,QSizePolicy,
                               QVBoxLayout,QWidget)

from assembly_effects import component_family
from assembly_inspection import COMPONENT_LABELS,snapshot as inspection_snapshot
from assembly_window import AssemblyWindow


class _MenuButton(QPushButton):
    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen);painter.setBrush(self.palette().color(QPalette.ButtonText))
        for offset in (-5,0,5):
            painter.drawEllipse(QRectF(self.width()/2+offset-1.1,self.height()/2-1.1,2.2,2.2))


class _ContrastLabel(QLabel):
    """A cached, static 0.8px contrasting text halo for unknown wallpapers."""
    _contrast=False

    def set_contrast(self,enabled):
        self._contrast=enabled is True;self.update()

    def paintEvent(self,event):
        if not self._contrast:return super().paintEvent(event)
        rect=self.contentsRect();key=(self.text(),self.font().toString(),rect.width(),self.wordWrap())
        if getattr(self,'_text_key',None)!=key:
            self._text_key=key;layout=QTextLayout(self.text(),self.font())
            option=QTextOption();option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere if self.wordWrap() else QTextOption.NoWrap)
            layout.setTextOption(option);path=QPainterPath();y=0.
            layout.beginLayout()
            while True:
                line=layout.createLine()
                if not line.isValid():break
                line.setLineWidth(max(1,rect.width()-2));line.setPosition(QPointF(0,y))
                path.addText(QPointF(1,y+line.ascent()),self.font(),self.text()[line.textStart():line.textStart()+line.textLength()])
                y+=line.height()
            layout.endLayout();self._text_path=path;self._text_height=y
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipRect(rect);painter.translate(rect.x(),rect.y()+max(0.,(rect.height()-self._text_height)/2))
        ink=self.palette().color(QPalette.WindowText)
        halo=QColor(10,18,26,210) if ink.lightness()>145 else QColor(255,255,255,215)
        painter.setPen(QPen(halo,1.6,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));painter.setBrush(ink)
        painter.drawPath(self._text_path)


class AssemblyWidgetWindow(AssemblyWindow):
    window_mode='desktop'

    def _initialize(self,controller,engine,spec,viewport_factory):
        if viewport_factory is None:
            from assembly_viewer import AssemblyViewport
            viewport_factory=AssemblyViewport
        self._initialize_state()
        self._desktop_frame=None;self._move_offset=None;self._context_menu=None
        self._dark=controller.theme=='dark'
        self.setObjectName('assemblyDesktopWidget')
        self.setWindowTitle(controller.tr('整机桌面小组件')+' · Desktop Stats')
        self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnBottomHint
                            |Qt.WindowDoesNotAcceptFocus|Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground,True)
        self.setAttribute(Qt.WA_ShowWithoutActivating,True)
        self.setAttribute(Qt.WA_DeleteOnClose,True)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMinimumSize(280,300);self.resize(420,480)
        ink='#e7edf2' if self._dark else '#293b49'
        muted='#aab8c4' if self._dark else '#60717e'
        self.setStyleSheet("QWidget{background:transparent;color:"+ink
            +";font-family:'Segoe UI','Microsoft YaHei UI';font-size:12px;}"
            +"QPushButton{border:0;padding:2px 6px;border-radius:5px;}"
            +"QPushButton:hover{background:"+('#384553' if self._dark else '#e4ebf0')+";}")
        self._layout=QVBoxLayout(self);self._layout.setSpacing(5)
        self._header=QWidget(self);self._header.setObjectName('assemblyDesktopHeader')
        header=QHBoxLayout(self._header);header.setContentsMargins(0,0,0,0);header.setSpacing(8)
        self.title=QLabel();self.title.setTextFormat(Qt.PlainText)
        self.title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.title.setStyleSheet('font-size:12px;font-weight:600;')
        header.addWidget(self.title,1)
        menu_button=_MenuButton();menu_button.setObjectName('assemblyDesktopMenuButton')
        menu_button.setAccessibleName(controller.tr('小组件菜单'));menu_button.setFocusPolicy(Qt.NoFocus)
        menu_button.setFixedSize(26,24);menu_button.clicked.connect(self._open_button_menu)
        header.addWidget(menu_button)
        self._layout.addWidget(self._header)
        self.viewport=viewport_factory(self);self.viewport.setObjectName('assemblyDesktopViewport')
        self.viewport.set_dark(self._dark);self.viewport.setMinimumSize(0,0)
        self.viewport.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.viewport.setFocusPolicy(Qt.NoFocus);self.viewport.setAutoFillBackground(False)
        if hasattr(self.viewport,'set_transparent_background'):self.viewport.set_transparent_background(True)
        self._layout.addWidget(self.viewport,1)
        self.fit_notice=_ContrastLabel();self.fit_notice.setTextFormat(Qt.PlainText);self.fit_notice.setWordWrap(True)
        self.fit_notice.setObjectName('assemblyDesktopFitNotice');self.fit_notice.setMaximumHeight(34)
        self.fit_notice.setStyleSheet('font-size:10px;color:'+('#e3c28c' if self._dark else '#8a5a23')+';')
        self.fit_notice.hide();self._layout.addWidget(self.fit_notice)
        self.components=_ContrastLabel();self.components.setTextFormat(Qt.PlainText)
        self.components.setObjectName('assemblyDesktopSelectedIdentity')
        self.components.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.components.setStyleSheet('font-size:11px;font-weight:600;')
        self._layout.addWidget(self.components)
        self.reading_summary=_ContrastLabel();self.reading_summary.setTextFormat(Qt.PlainText)
        self.reading_summary.setObjectName('assemblyDesktopReadings');self.reading_summary.setWordWrap(True)
        self.reading_summary.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self._layout.addWidget(self.reading_summary)
        self.status=_ContrastLabel();self.status.setTextFormat(Qt.PlainText)
        self.status.setObjectName('assemblyDesktopMotionStatus');self.status.setWordWrap(True)
        self.status.setMaximumHeight(30);self.status.setStyleSheet('font-size:10px;color:'+muted+';')
        self._layout.addWidget(self.status)
        for item in (self,self.viewport,self._header,self.title,self.components,self.reading_summary,self.status):
            item.installEventFilter(self)
        self.viewport.componentSelected.connect(self._component_selected)
        self.viewport.rendererError.connect(self._render_failed)
        self.viewport.animationActiveChanged.connect(self._clock_active)
        self._attach_session(controller,engine,spec)

    def synchronize(self,spec):
        if not self._apply_scene(spec):return
        self._apply_motion_options(spec['options'])
        self.title.setText(self.controller.tr(spec['case']['label']))
        self._set_frame(spec['options'].get('desktop_frame',True))
        self.fit_notice.setToolTip(self.fit_notice.text())
        self.update_readings()

    def _set_frame(self,enabled):
        enabled=enabled is True
        if self._desktop_frame==enabled:return
        self._desktop_frame=enabled
        self._header.setVisible(enabled)
        self.inspection_state=None
        for label in (self.fit_notice,self.components,self.reading_summary,self.status):
            label.set_contrast(not enabled)
        self._layout.setContentsMargins(*( (14,10,14,12) if enabled else (8,4,8,6) ))
        self.update()

    def paintEvent(self,event):
        # Paint only the optional card. An unframed top level and its FBO both
        # leave alpha zero outside the model and the antialiased text pixels.
        if not self._desktop_frame:return
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor('#202a34' if self._dark else '#f3f6f9'))
        painter.setPen(QPen(QColor('#425160' if self._dark else '#d1dce4'),1.))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),14,14)

    def _refresh_part_choices(self):
        # The compact view has no hidden inspector/editor controls.
        pass

    def _component_selected(self,name):
        if self._closing:return
        name=name if name=='all' or self._part_family(name)!='all' else 'all'
        changed=name!=self.selected_component;self.selected_component=name
        if changed or self.inspection_state is None:self._update_inspection()
        self._sync_part_assembly();self._sync_gpu_assembly()

    def _update_inspection(self):
        if self._closing or not self._spec or not self.isVisible() or self.isMinimized():return
        state=inspection_snapshot(getattr(self.controller,'readings',{}),self._spec,
            getattr(self.controller,'draft',{}),self.selected_component,
            scene_metadata=getattr(getattr(self.viewport,'scene',None),'metadata',{}))
        if state==self.inspection_state:return
        self.inspection_state=state
        family=self._part_family()
        identity=(self.controller.tr('整机概览') if self._desktop_frame else self._spec['case']['label']) if family=='all' else ' · '.join(state['identity_parts'])
        self.components.setText(self.controller.tr(identity));self.components.setToolTip(self.controller.tr(identity))
        if family=='all':
            wanted={'cpu_usage','cpu_temp','gpu_usage','gpu_temp'}
            rows=[row for row in state['rows'] if row.get('metric') in wanted]
        elif family in ('cpu','gpu'):
            wanted={family+'_usage',family+'_temp',family+'_power'}
            rows=[row for row in state['rows'] if row.get('metric') in wanted]
        else:rows=state['rows'][:3]
        self.reading_summary.setText('  ·  '.join(self.controller.tr(row['label'])+' '+self.controller.tr(row['value']) for row in rows))
        self.reading_summary.setToolTip('\n'.join(self.controller.tr(row['label'])+': '+
            ' · '.join(self.controller.tr(v) for v in (row['value'],row.get('reason',''),row.get('source','')) if v)
            for row in rows))

    def eventFilter(self,watched,event):
        kind=event.type()
        if kind==QEvent.ContextMenu:
            self._show_menu(event.globalPos());event.accept();return True
        if kind==QEvent.MouseButtonPress and event.button()==Qt.LeftButton:
            if event.modifiers()&Qt.AltModifier or watched in (self._header,self.title):
                self._move_offset=event.globalPosition().toPoint()-self.pos()
                event.accept();return True
        if kind==QEvent.MouseMove and self._move_offset is not None:
            self.move(event.globalPosition().toPoint()-self._move_offset);event.accept();return True
        if kind==QEvent.MouseButtonRelease and self._move_offset is not None:
            self._move_offset=None;event.accept();return True
        if kind in (QEvent.Hide,QEvent.WindowDeactivate):self._move_offset=None
        return super().eventFilter(watched,event)

    def _open_button_menu(self):
        button=self.sender()
        self._show_menu(button.mapToGlobal(QPoint(0,button.height())))

    def _select_part(self,identity):
        self.viewport.select_component(identity)

    def _show_menu(self,position):
        if not self._can_interact():return
        if self._context_menu is not None:self._context_menu.close()
        menu=QMenu(self);self._context_menu=menu
        menu.setStyleSheet('QMenu{background:'+('#263340' if self._dark else '#f7fafc')
            +';padding:6px;border:1px solid '+('#465564' if self._dark else '#ccd9e2')
            +';border-radius:6px;} QMenu::item{padding:6px 18px;} QMenu::item:selected{background:'
            +('#405365' if self._dark else '#e0edf4')+';}')
        frame=menu.addAction(self.controller.tr('显示小组件边框'));frame.setCheckable(True)
        frame.setChecked(self._desktop_frame)
        frame.triggered.connect(lambda value:self.controller.changeAssembly('desktop_frame',value))
        show_psu=menu.addAction(self.controller.tr('展示电源'));show_psu.setCheckable(True)
        show_psu.setChecked(bool(self._spec and self._spec.get('options',{}).get('show_psu')))
        show_psu.setToolTip(self.controller.tr('有电源仓时临时移开遮罩；开放式机箱仍按实际布局显示。'))
        show_psu.triggered.connect(lambda value:self.controller.changeAssembly('show_psu',value))
        parts=QMenu(self.controller.tr('查看部件'),menu);menu.addMenu(parts)
        for identity,label in COMPONENT_LABELS.items():
            action=parts.addAction(self.controller.tr(label));action.setCheckable(True)
            action.setChecked(self.selected_component==identity)
            action.triggered.connect(lambda _checked=False,key=identity:self._select_part(key))
        metadata=getattr(getattr(self.viewport,'scene',None),'metadata',{})
        for group in ('hardware','cooling','auxiliary'):
            for row in metadata.get(group,{}).get('parts',()):
                if not isinstance(row,dict) or not row.get('id') or not row.get('label'):continue
                action=parts.addAction(row['label'])
                action.triggered.connect(lambda _checked=False,key=row['id']:self._select_part(key))
        menu.addAction(self.controller.tr('重置视角'),self.viewport.reset_camera)
        kind=self._part_family()
        if kind in ('cpu','memory','fans'):
            state=self._part_assembly_state()
            for label,removed,name in (('取出查看',True,'assemblyPartRemoveAction'),('插回原位',False,'assemblyPartInsertAction')):
                action=menu.addAction(self.controller.tr(label),lambda _checked=False,value=removed:self._preview_part_motion(value))
                action.setObjectName(name)
                action.setEnabled(state.get('available') is True and not state.get('active')
                                  and (state.get('progress',0.)<1. if removed else state.get('progress',0.)>0.))
                action.setToolTip(self.controller.tr('仅沿已核参考方向分离；未模拟固定件和插头操作，不代表完整出箱。')
                                  if state.get('available') else self._part_assembly_reason(state))
            if kind=='fans':
                release=menu.addAction(self.controller.tr('参考解除安装固定与连接'));release.setObjectName('assemblyPartMountReleaseAction')
                release.setCheckable(True);release.setChecked(self.selected_component in state.get('released_mounts',()))
                release.setEnabled(self.selected_component in state.get('allowed_mount_release_part_ids',()) and not state.get('active')
                    and state.get('reason') not in ('motion_disabled','return_other_part_first','close_exploded_view'))
                release.triggered.connect(self._toggle_mount_release)
            else:
                retention=menu.addAction(self.controller.tr('暂时隐藏固定扣具'));retention.setObjectName('assemblyPartRetentionAction')
                retention.setCheckable(True);retention.setChecked(state.get('retention_hidden') is True)
                retention.setEnabled(bool(state.get('allowed_opened_mesh_names')) and not state.get('active'))
                retention.triggered.connect(self._toggle_retention)
        elif kind in ('all','gpu'):
            gpu_state=self._gpu_assembly_state()
            for label,removed in (('拔出查看',True),('插回插槽',False)):
                action=menu.addAction(self.controller.tr(label),lambda _checked=False,value=removed:self._preview_gpu_insertion(value))
                action.setEnabled(gpu_state.get('available') is True and not gpu_state.get('active')
                                  and (gpu_state.get('progress',0.)<1. if removed else gpu_state.get('progress',0.)>0.))
                action.setToolTip(self.controller.tr('沿插槽方向移动；未模拟螺丝、卡扣及电源线拔插。')
                                  if gpu_state.get('available') else self._gpu_assembly_reason(gpu_state))
        state=self._part_assembly_state()
        hide_part=menu.addAction(self.controller.tr('暂时隐藏此部件'));hide_part.setObjectName('assemblyPartHiddenAction')
        hide_part.setCheckable(True);hide_part.setChecked(self.selected_component in state.get('hidden_parts',()))
        hide_part.setEnabled(self.selected_component!='all' and callable(getattr(self.viewport,'set_part_hidden',None)))
        hide_part.triggered.connect(self._toggle_part_hidden)
        restore=menu.addAction(self.controller.tr('全部显示'));restore.setObjectName('assemblyRestoreHiddenAction')
        restore.setEnabled(bool(state.get('hidden_parts')) or state.get('retention_hidden') is True or bool(state.get('released_mounts')))
        restore.triggered.connect(self._restore_hidden)
        size_menu=QMenu(self.controller.tr('小组件大小'),menu);menu.addMenu(size_menu)
        menu._submenus=(parts,size_menu)
        for label,size in (('紧凑尺寸',(320,380)),('标准尺寸',(420,480)),('大尺寸',(520,600))):
            size_menu.addAction(self.controller.tr(label),lambda _checked=False,value=size:self.resize(*value))
        menu.addSeparator()
        menu.addAction(self.controller.tr('打开完整检视'),self.controller.openAssemblyInspect)
        menu.addAction(self.controller.tr('关闭小组件'),self.close)
        menu.aboutToHide.connect(menu.deleteLater)
        menu.destroyed.connect(lambda:self._clear_menu(menu))
        menu.popup(position)

    def _clear_menu(self,menu):
        if self._context_menu is menu:self._context_menu=None

    def _dispose(self):
        if getattr(self,'_context_menu',None) is not None:
            self._context_menu.close();self._context_menu=None
        super()._dispose()
