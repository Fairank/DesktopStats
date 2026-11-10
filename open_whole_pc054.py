"""Lazy approved whole-PC source-world packet, with no runtime glTF codec.

Adapter code follows the application LICENSE. The imported PC Components
Manual model remains MIT as declared in its original README; meshoptimizer
retains its MIT notice. No application NC restriction or watermark is added.
"""
import math
from types import MappingProxyType

from open_reference_models054 import ModelError, ReferenceModel, _json, _sha, _srgb


MANIFEST_FILE = 'whole-pc-reference054.json'
MANIFEST_BYTES = 134531
MANIFEST_SHA256 = '14d40b608c29cda125274d0a1f1d122733030861af5b42ccb919bd959505d52d'
MODEL_ID = 'pc-components-manual-whole-PC-basepose054'
SOURCE_URL = 'https://github.com/mdrayyanhussain2006/pc-components-manual/tree/1aabb3b1a537f47b2d91d83e9113cd9454013c1e'
ATTRIBUTION = 'PC Components Manual · mdrayyanhussain2006 · MIT（上游README声明）；meshoptimizer · MIT'
FILES = (
    ('whole-pc-basepose054.bin', 2403576, '7600c2f1d9dcab468724ad9debad748da3939ab96e7f3e2a843ef4b24f5a0df5'),
    ('source-original.glb', 539272, '221d028bbaa5820ae7957ceb26a1e0ce88f98f682d37fb58d018d892f7846e7c'),
    ('source-decoded054.gltf', 142554, '380708d2dea128f71c4291b8b253f8794466778fcdee35a2362d8cb87938e543'),
    ('decoded-views054.bin', 978608, '56c3155124517a910b2d922e2d18ad5dde4cfb07c7e6ef30a1421787a9b1f1ac'),
    ('UPSTREAM-README.md', 9640, '30f429d211b4efe5f6e9f72471057005ad8c8994e7318542a392d8e7efff7703'),
    ('SOURCE054.json', 791, 'e0fe1004d1736ccafd9b8d8daa60935dbd9fedd166493d459025c74c49296d9e'),
    ('LICENSE-meshoptimizer.md', 1079, 'f03037ca7bad1e3eb7f4a63fa6084a8baabd5ba30d3c239a9a7f35705d873e26'),
)
_COMPONENTS = frozenset(('case', 'cpu', 'cooler', 'fans', 'gpu', 'board', 'psu', 'memory', 'storage', 'cables'))
_LIMITS = (
    '通用开源教学台式机，不对应本机品牌、型号或经厂商核准的制造尺寸。',
    '当前显示原始初始装配姿态；没有绑定本机传感器或播放拆装时间线。',
    '原动画、形变和材质数据保留在包中；当前颜色因子着色未完整还原玻璃透射与PBR。',
)


def _require(value, message):
    if not value:
        raise ModelError(message)


def verify_sources(package):
    """Check exact original declaration and decoder notice, not merely existence."""
    packed = None
    for name, size, checksum in FILES:
        raw = package.verify(name, size, checksum)
        # Keep validation independent from a package-like caller's behaviour.
        _require(len(raw) == size and _sha(raw) == checksum, '开源整机文件校验不匹配：' + name)
        if name == 'whole-pc-basepose054.bin':
            packed = raw
    return packed


def from_package(package):
    """Read exactly one reviewed packet through the existing safe ZIP reader."""
    raw = package.read(MANIFEST_FILE, MANIFEST_BYTES)
    _require(len(raw) == MANIFEST_BYTES and _sha(raw) == MANIFEST_SHA256,
             '此整机模型尚未纳入已核对的开源参考包。')
    doc = _json(raw)
    _require(doc.get('format') == 'DesktopStats.open-whole-PC-basepose.054.1'
             and doc.get('model_id') == MODEL_ID and doc.get('attribution') == ATTRIBUTION
             and doc.get('source_urls') == [SOURCE_URL], '开源整机来源与核对记录不一致。')
    _require(doc.get('physical_draws') == 67 and doc.get('triangles') == 33383
             and len(doc.get('parts', ())) == 25 and len(doc.get('draws', ())) == 67,
             '开源整机部件或几何数量不一致。')
    packed = verify_sources(package)
    _require(type(packed) is bytes, '开源整机需保留不可变几何缓冲。')
    from assembly_geometry import Mesh, Scene
    part_index = {row['id']: row for row in doc['parts']}
    _require(len(part_index) == 25 and all(identity.startswith('reference:') for identity in part_index),
             '开源整机独立部件标识无效。')
    cursor = 0
    meshes = []
    for row in doc['draws']:
        length, count, start = row.get('bytes'), row.get('vertex_count'), row.get('offset')
        _require(type(length) is int and type(count) is int and type(start) is int
                 and start == cursor and count > 0 and count % 3 == 0
                 and length == count * 24 and start + length <= len(packed),
                 '开源整机几何范围无效。')
        identity = row['part_id']
        _require(identity in part_index and row['component'] in _COMPONENTS
                 and row['component'] == part_index[identity]['kind'],
                 '开源整机几何与部件不匹配。')
        vertices = memoryview(packed)[cursor:cursor + length].cast('f')
        _require(vertices.readonly and vertices.obj is packed and all(math.isfinite(v) for v in vertices),
                 '开源整机含无效坐标。')
        rgba = row['source_RGBA_linear']
        meshes.append(Mesh(row['name'], vertices, _srgb(rgba[:3], rgba[3]),
                           component=row['component'], part_id=identity))
        cursor += length
    _require(cursor == len(packed) and sum(m.vertex_count for m in meshes) // 3 == 33383,
             '开源整机缓冲区覆盖不完整。')
    low = tuple(min(min(m.vertices[a::6]) for m in meshes) for a in range(3))
    high = tuple(max(max(m.vertices[a::6]) for m in meshes) for a in range(3))
    _require(list(low) == doc['reference_bounds']['minimum']
             and list(high) == doc['reference_bounds']['maximum'], '开源整机范围与记录不一致。')
    metadata = dict(reference_only=True, visual_style='miniature', reference_model_id=MODEL_ID,
                    source_license=doc['source_license'], source_url=SOURCE_URL,
                    dimensions_verified=False, mechanical_fit_verified=False, telemetry_bound=False,
                    source_quality_accepted=False, reference_bounds=dict(minimum=low, maximum=high),
                    hardware=dict(parts=doc['parts']), cooling=dict(cpu_fan_tach_usable=False, real_cpu_rotor_parts=()),
                    source_materials=doc['source_materials'],
                    source_draw_materials=[row['source_material'] for row in doc['draws']],
                    default_morphs=doc['default_morphs'], timeline_evaluated=False,
                    material_limit=doc['runtime_material_limit'])
    scene = Scene(tuple(meshes), tuple(max(.01, b - a) for a, b in zip(low, high)), metadata)
    return ReferenceModel(MODEL_ID, doc['label'], scene,
                          tuple(MappingProxyType(dict(row)) for row in doc['parts']),
                          ATTRIBUTION, (SOURCE_URL,), _LIMITS, len(packed), FILES[1][2], ('',) * 67)
