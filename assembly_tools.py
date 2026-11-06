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

    def __init__(self):
        super().__init__()
        self._assembly_page_active = False
        self._assembly_viewer_active = False
        self._assembly_firmware = None
        self._assembly_modules = None
        self._assembly_fingerprint = None
        self._assembly_spec = None
        self._assembly_summary = dict(initialized=False)

    def initialize_assembly_signals(self):
        self.dataChanged.connect(self._refresh_assembly)
        self.draftChanged.connect(self._refresh_assembly)
        self.languageChanged.connect(self.assemblyCasesChanged)

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

    @Slot(str, "QVariant")
    def changeAssembly(self, field, selected):
        if field not in ("case_model", "exploded", "fan_animation", "appearance_style", "detail_level", "selection_effects"):
            return
        value = copy.deepcopy(self._draft)
        value["assembly"][field] = selected
        self.edit(value, merge_key=("assembly", field))

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

    def assembly_specification(self):
        self._refresh_assembly()
        return copy.deepcopy(self._assembly_spec) if self._assembly_spec else None

    def assembly_fan_state(self):
        return fan_state(self._data, self._draft)
