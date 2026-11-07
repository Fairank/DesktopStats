"""Lazy assembly-view state layered on the existing scoped settings controller."""
import copy

from PySide6.QtCore import Property, Signal, Slot

from assembly_spec import build_spec, component_fingerprint, fan_state, summary
from assembly_config import detail_choices,style_choices
from workspace_tools import WorkspaceTools


class AssemblyTools(WorkspaceTools):
    assemblyChanged = Signal()
    assemblyCasesChanged = Signal()
    assemblyViewRequested = Signal(dict)
    hardwarePacksChanged = Signal()

    def __init__(self):
        super().__init__()
        self._assembly_page_active = False
        self._assembly_viewer_active = False
        self._assembly_firmware = None
        self._assembly_modules = None
        self._assembly_fingerprint = None
        self._assembly_spec = None
        self._assembly_summary = dict(initialized=False)
        self._pack_status = ''
        self._accessory_gallery_active = False

    def initialize_assembly_signals(self):
        self.dataChanged.connect(self._refresh_assembly)
        self.draftChanged.connect(self._refresh_assembly)
        self.languageChanged.connect(self.assemblyCasesChanged)
        self.languageChanged.connect(self.hardwarePacksChanged)

    @Property('QVariantMap', notify=hardwarePacksChanged)
    def hardwarePacks(self):
        from hardware_packs import runtime_store
        store=runtime_store()
        return dict(installed=store.installed(),status=self.tr(self._pack_status) if self._pack_status else '',
                    invalid=bool(store.errors),**store.memory_status())

    def _hardware_packs_updated(self):
        from cpu_package_runtime import _match_identity
        _match_identity.cache_clear()
        import sys
        gallery=sys.modules.get('accessory_art')
        if gallery is not None:gallery.clear_cache()
        self._assembly_fingerprint=None
        self._refresh_assembly()
        self.hardwarePacksChanged.emit()
        self.assemblyCasesChanged.emit()
        self.dataChanged.emit()

    @Slot()
    def openHardwarePacksDownload(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from hardware_packs import PACK_RELEASE_URL
        QDesktopServices.openUrl(QUrl(PACK_RELEASE_URL))

    @Slot()
    def importHardwarePack(self):
        from PySide6.QtWidgets import QFileDialog
        from hardware_packs import runtime_store,PackError
        path,_=QFileDialog.getOpenFileName(None,self.tr('导入硬件扩展包'),'', 'DesktopStats (*.dspack)')
        if not path:return
        try:
            runtime_store().install(path)
            self._pack_status='扩展包已安装，新增型号已可选择。'
        except (OSError,PackError):
            self._pack_status='扩展包无效或超出限制，原目录保持不变。'
        self._hardware_packs_updated()

    @Slot(str)
    def removeHardwarePack(self,pack_id):
        from hardware_packs import runtime_store,PackError
        try:
            removed=runtime_store().remove(pack_id)
            self._pack_status='扩展包已移除，本机采集保持正常。' if removed else ''
        except (OSError,PackError):
            self._pack_status='未能移除扩展包，请重试。'
        self._hardware_packs_updated()

    def _ensure_assembly_identity(self):
        if self._assembly_firmware is None:
            from chassis_identity import snapshot
            from memory_identity import modules
            self._assembly_firmware = snapshot()
            self._assembly_modules = modules()

    def _refresh_assembly(self):
        if not (self._assembly_page_active or self._assembly_viewer_active):
            return
        self._ensure_assembly_identity()
        fingerprint = component_fingerprint(self._data, self._draft, self._assembly_firmware, self._assembly_modules)
        if fingerprint == self._assembly_fingerprint:
            return
        self._assembly_spec = build_spec(self._data, self._draft, self._assembly_firmware, self._assembly_modules)
        self._assembly_summary = summary(self._assembly_spec)
        self._assembly_fingerprint = fingerprint
        self.assemblyChanged.emit()

    @Slot(bool)
    def setAssemblyActive(self, active):
        self._assembly_page_active = active is True
        if active:
            self._refresh_assembly()

    def set_assembly_viewer_active(self, active):
        self._assembly_viewer_active = bool(active)
        if active:
            self._refresh_assembly()

    assemblySummary = Property("QVariantMap", lambda self: copy.deepcopy(self._assembly_summary), notify=assemblyChanged)

    @Property("QVariantList", notify=assemblyCasesChanged)
    def assemblyCases(self):
        from chassis_catalog import choices
        return [dict(id="", label=self.tr("自动识别 / 参考机箱")), *choices()]

    @Property("QVariantList", notify=assemblyCasesChanged)
    def assemblyStyles(self):
        return style_choices(self.tr)

    @Property("QVariantList", notify=assemblyCasesChanged)
    def assemblyDetails(self):
        return detail_choices(self.tr)

    @Property("QVariantMap", notify=assemblyCasesChanged)
    def assemblyParts(self):
        from assembly_parts import choices
        return choices(self.tr)

    @Property('QVariantMap', notify=assemblyCasesChanged)
    def accessoryCatalog(self):
        from accessory_art import choices
        return choices()

    @Slot(str,str,str,result='QVariantMap')
    def accessoryModelArt(self,kind,model,style):
        from accessory_art import art
        return art(kind,model,style)

    @Slot(bool)
    def setAccessoryGalleryActive(self,active):
        self._accessory_gallery_active=active is True
        if not self._accessory_gallery_active:
            from accessory_art import clear_cache
            clear_cache()

    @Slot(str)
    def downloadAccessoryArt(self,kind):
        keys={'case':'cases','cooler':'coolers','psu':'psus','fan':'fans'}
        if not isinstance(kind,str) or kind not in keys:return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from product_version import VERSION
        QDesktopServices.openUrl(QUrl('https://github.com/Fairank/DesktopStats/releases/download/models-v'+VERSION
            +'/DesktopStats-'+VERSION+'-'+keys[kind]+'-SVG.zip'))

    @Property("QVariantList", notify=assemblyCasesChanged)
    def assemblyStyleTargets(self):
        from assembly_inspection import COMPONENT_LABELS
        return [dict(id=key,label=self.tr(label)) for key,label in COMPONENT_LABELS.items() if key!='all']

    @Slot(str,str)
    def changeAssemblyPartStyle(self,target,style):
        value=copy.deepcopy(self._draft)
        if style=='follow':value['assembly']['part_styles'].pop(target,None)
        else:value['assembly']['part_styles'][target]=style
        self.edit(value,merge_key=('assembly','style',target))

    @Slot()
    def resetAssemblyPartStyles(self):
        value=copy.deepcopy(self._draft)
        value['assembly']['part_styles']={}
        self.edit(value,merge_key=('assembly','styles'))

    @Slot(str, "QVariant")
    def changeAssembly(self, field, selected):
        from assembly_config import PART_FIELDS
        if field not in ("case_model", "exploded", "fan_animation", "appearance_style", "detail_level", "selection_effects",
                         "window_mode", "desktop_frame",*PART_FIELDS):
            return
        value = copy.deepcopy(self._draft)
        value["assembly"][field] = selected
        self.edit(value, merge_key=("assembly", field))

    @Slot(str)
    def useAssemblyReference(self,kind):
        from assembly_parts import reference_preset
        if kind not in ('air','aio','loop'):return
        value=copy.deepcopy(self._draft)
        value['assembly']=reference_preset(value['assembly'],kind)
        self.edit(value,merge_key=('assembly','reference'))

    @Slot(str,str,int,str)
    def changeAssemblyFan(self,mount,model,count,direction):
        # One complete detached group edit, preserving all other mount groups.
        from assembly_config import FAN_MOUNTS
        if mount not in FAN_MOUNTS:return
        value=copy.deepcopy(self._draft)
        rows=[row for row in value['assembly']['case_fans'] if row['mount']!=mount]
        if model:rows.append(dict(model=model,mount=mount,count=count,direction=direction))
        value['assembly']['case_fans']=rows
        self.edit(value,merge_key=('assembly','fan',mount))

    @Slot(str,int)
    def changeAssemblyStorage(self,model,count):
        value=copy.deepcopy(self._draft)
        rows=[row for row in value['assembly']['storage'] if row['model_id']!=model]
        if count:rows.append(dict(model_id=model,count=count))
        value['assembly']['storage']=rows
        self.edit(value,merge_key=('assembly','storage',model))

    @Slot(str,bool)
    def changeAssemblyExpansion(self,model,enabled):
        value=copy.deepcopy(self._draft)
        rows=[row for row in value['assembly']['expansion_cards'] if row['model_id']!=model]
        if enabled:rows.append(dict(model_id=model))
        value['assembly']['expansion_cards']=rows
        self.edit(value,merge_key=('assembly','expansion',model))

    @Slot(int,str)
    def changeAssemblyMemory(self,index,model):
        value=copy.deepcopy(self._draft);models=value['assembly']['memory_models']
        if index==-1:
            if len(models)>=8 or not model:return
            models.append(model)
        elif 0<=index<len(models):
            if model:models[index]=model
            else:models.pop(index)
        else:return
        self.edit(value,merge_key=('assembly','memory',index))

    @Slot()
    def resetAssemblyMemory(self):
        self.changeAssembly('memory_models',[])

    @Slot()
    def openAssemblyView(self):
        self._ensure_assembly_identity()
        before = self._assembly_page_active
        self._assembly_page_active = True
        try:
            self._refresh_assembly()
        finally:
            self._assembly_page_active = before
        self.assemblyViewRequested.emit(copy.deepcopy(self._assembly_spec))

    @Slot()
    def openAssemblyDesktop(self):
        self.changeAssembly('window_mode','desktop')
        self.openAssemblyView()

    @Slot()
    def openAssemblyInspect(self):
        self.changeAssembly('window_mode','inspect')
        self.openAssemblyView()

    def assembly_specification(self):
        self._refresh_assembly()
        return copy.deepcopy(self._assembly_spec) if self._assembly_spec else None

    def assembly_fan_state(self):
        if self._assembly_spec and self._assembly_spec.get('gpu',{}).get('telemetry_bound') is False:
            return dict(available=False,rpm=None)
        return fan_state(self._data, self._draft)

    def assembly_cpu_fan_state(self):
        if self._assembly_spec and self._assembly_spec.get('cpu',{}).get('telemetry_bound') is False:
            return dict(available=False,rpm=None)
        from assembly_feedback import cpu_fan_state
        return cpu_fan_state(self._data)
