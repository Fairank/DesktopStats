"""One owned geometry snapshot; palette changes never reroute or rebuild parts."""
import json

from assembly_geometry import Scene,build_scene
from assembly_style import apply_model_styles,resolve_style

PHYSICAL_FIELDS=('case','gpu','cpu','memory','board','cooling','auxiliary','detail_level','detail_focus','model_library_generation')


class SceneCache:
    def __init__(self):
        self.key=None;self.base=None

    def build(self,spec):
        from assembly_cache_projection056 import cache_key_input
        from assembly_packed_vertices056 import compact_scene
        physical={key:spec[key] for key in PHYSICAL_FIELDS if key in spec}
        key=json.dumps(cache_key_input(physical),sort_keys=True,ensure_ascii=True)
        if key!=self.key:
            base=build_scene(dict(physical,visual_style='miniature',part_styles={}))
            self.base=compact_scene(base);self.key=key
        style=resolve_style(spec.get('visual_style'));overrides=spec.get('part_styles') or {}
        lighting=spec.get('lighting_preview','artwork')
        if style=='miniature' and not overrides and lighting=='artwork':return self.base
        case=spec.get('case') or {}
        meshes,metadata=apply_model_styles(self.base.meshes,style,overrides,self.base.dimensions,case.get('panels') or {},lighting,
            finish_materials=self.base.metadata.get('motherboard',{}).get('finish_materials'))
        return compact_scene(Scene(meshes,self.base.dimensions,dict(self.base.metadata,**metadata)))

    def clear(self):
        self.base=None;self.key=None
