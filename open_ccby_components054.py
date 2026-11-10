"""Lazy approved CC BY CPU/GPU packets; no runtime codec, image decoder or I/O.

Application adapter code follows the application LICENSE. Model authors retain
CC BY 4.0 rights; this code adds neither an NC override nor an ownership mark.
The GPU preserves a reviewed compact LOD, not the original full-detail mesh.
"""
import math
from types import MappingProxyType

from open_reference_models054 import ModelError, ReferenceModel, _json, _sha, _srgb

MANIFEST_FILE = 'reference054.json'
CC_BY_URL = 'https://creativecommons.org/licenses/by/4.0/'
_NOTICES = (
    ('LICENSE-CC-BY-4.0.txt', 18657, '9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411'),
    ('ATTRIBUTION053.md', 4579, 'c456da7ea24fc112b59faedf2f2414f35c463094d9db651c12b4190d55e47801'),
    ('MODEL_SOURCES053.json', 19203, '9a477523d717c8396c5ea9d314c5decaaf23f3f3dea9cb1a21477f1dc5569ec3'),
    ('UPSTREAM-MODEL-CREDITS.md', 3559, '18c94be30e8c8fbee79bf1ace321e2aadd5e7f545875c36ced3821e77ae1fbfa'),
)
APPROVED = {
    '733bfe8d09420baabc2520a3eda3a16b32a72755fde1e9061cfbb5b53f8db426': dict(
        asset='cpu', manifest_bytes=9368, draws=2, triangles=426, nodes=4, meshes=2,
        source_sha256='98f5a17c4c8a7130f68fef110088312fd4edc77f84c0fdbfdb14f2eed81a4818',
        indexed_sha256='415e80d2dd4f0a91918248fb00d0361e746dcd9931e385ce76a38956b63f7489',
        source_url='https://sketchfab.com/3d-models/efb6b95b255c4a37a9661df178ea3bb3',
        attribution='PC CPU processor · apleesee · CC BY 4.0', parent_sha256=None, lod_sha256=None),
    'bce17130167b2cfb6c2f92d991ab1342e1dbb2cec8da3e6efcb8eecaa68328f6': dict(
        asset='gpu', manifest_bytes=56885, draws=27, triangles=56742, nodes=67, meshes=27,
        source_sha256='027b9135933e71839572007c5cd5208a137da598ab8d122f64bacaaf3682522b',
        indexed_sha256='8722e2ebf3d3336eed97229c2433547a9c2e3cb42cc6b2b8462def4bf6e25f8f',
        source_url='https://sketchfab.com/3d-models/geforce-rtx-3080-graphics-card-8b947ee1bf7a4e3d8ffa1c24893ac160',
        attribution='GeForce RTX 3080 Graphics Card · _surovic_ / samuelsurovic · CC BY 4.0',
        parent_sha256='7662c59ec1332c804eed0554a62bac663320d16899ab1bf1ec14f908b060e7b9',
        lod_sha256='01822c53e1b74bb7fc79ce78a63b4c7d556d780703966e6ed8db823055c20394'),
}
FILES = {
    'cpu': (
        ('world-PN054.bin', 30672, 'eba6f94a56cef9af9d95843de902e7c35c7697c2071d0176e17cf827ded4371a'),
        ('geometry053.bin', 23516, 'a23db899c93c21e8276abef11a1b146ebbfe49e8ce6f843201e552185dd2eacc'),
        ('tangent053.bin', 8176, '186984c0a17045bbcd8d65ae0896437da747f727c58c90bf4f3d5ccd9cfa73a8'),
        ('image-0.webp', 104218, '3d73d36bb0d60fbdb50fe0f84776b9c20de34d0abef222e81e24f4d2998ebc6c'),
        ('image-1.webp', 8712, '1b27b5174f2e5157570e22f07d203dfb3655151c5e401e0ab2d715a75cd7c725'),
        ('image-2.webp', 2268, '4786840a0c7fe496fc3615daeb808f2fcbce58bdaaaaa151317c05dfb9901a5d'),
        ('image-3.webp', 36344, '3e99e1f9851c9f18d259155465e33de99226c76ac0f0b50ec805f359b466eaf9'),
        ('image-4.webp', 73660, 'ac6d661486f45eb98c7ae1f4805fac69591f976878e262b7c48a71b02d512c00'),
        ('color053.bin', 0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
        ('mesh053.json', 11506, '415e80d2dd4f0a91918248fb00d0361e746dcd9931e385ce76a38956b63f7489'),
        ('source-original.glb', 239048, '98f5a17c4c8a7130f68fef110088312fd4edc77f84c0fdbfdb14f2eed81a4818'),
        ('CHANGES054.txt', 505, '964fee70f73964dd63a0aa8927498ba6c19889c27dd934276c8d468c4aa0cc53'),
    ) + _NOTICES,
    'gpu': (
        ('world-PN054.bin', 4085424, '33869c0d61c124f26fb69fbbed457a850c51342e1c6cbd72571a78d619feb7d2'),
        ('geometry053.bin', 2215588, '9563243ac074fe109ac26a424cf68904dbef491ce044f9b6fa3232da7cb8b78b'),
        ('tangent053.bin', 937568, '97b29536b2c4b6561e522beec11ac21dc728fff8b0b972cf82bc1b42ecd12b14'),
        ('image-0.webp', 55652, '99bb8d8854cbe9dffe4a6a534aad81adddf525739a49623652c72595c8a5215a'),
        ('image-1.webp', 131608, 'd23cc273ef165a485f7a14245a6817163d613aa2a87759d6a844edb2bf85862f'),
        ('image-2.webp', 10448, '5a2dde0dc9872bf82baaf6221c9f0445fc726738786933ab07409a77f762a3a9'),
        ('image-3.webp', 1946, '62de64a571119da5ffb6a7aa740f04b1aed792f24f13357ff8d445e71242761a'),
        ('mesh053.json', 150257, '8722e2ebf3d3336eed97229c2433547a9c2e3cb42cc6b2b8462def4bf6e25f8f'),
        ('source-original.glb', 1412620, '027b9135933e71839572007c5cd5208a137da598ab8d122f64bacaaf3682522b'),
        ('CHANGES054.txt', 600, '8f86555cd9773e17746f04b3c354129076d4838f9608c2ec7da79d96ac6b3922'),
    ) + _NOTICES,
}


def _require(value, message):
    if not value:
        raise ModelError(message)


def verify_files(package, asset):
    """Verify required rights/source bytes; retain PN only, decode no images."""
    packed = None
    for name, size, checksum in FILES[asset]:
        raw = package.verify(name, size, checksum)
        _require(len(raw) == size and _sha(raw) == checksum, '开源硬件文件校验不匹配：' + name)
        if name == 'world-PN054.bin':
            packed = raw
        raw = None
    return packed


def validate_source_identity(doc, approved):
    _require(doc.get('format') == 'DesktopStats.open-CCBY-world-PN.054.1'
             and doc.get('asset') == approved['asset']
             and doc.get('source_license') == 'CC-BY-4.0'
             and doc.get('attribution') == approved['attribution']
             and doc.get('source_urls') == [approved['source_url'], CC_BY_URL]
             and doc.get('source_original_sha256') == approved['source_sha256']
             and doc.get('source_indexed_metadata_sha256') == approved['indexed_sha256']
             and doc.get('source_parent_metadata_sha256') == approved['parent_sha256']
             and doc.get('source_lod_indices_sha256') == approved['lod_sha256'],
             '开源硬件来源、署名或LOD记录不一致。')
    _require(all(doc.get(key) is False for key in ('dimensions_verified', 'mechanical_fit_verified',
             'telemetry_bound', 'source_quality_accepted', 'auto_play', 'watermark_applied', 'NC_override')),
             '开源参考不可标为实测、自动装配或附加许可限制。')


def from_package(package):
    raw = package.read(MANIFEST_FILE, max(row['manifest_bytes'] for row in APPROVED.values()))
    approved = APPROVED.get(_sha(raw))
    _require(approved is not None and len(raw) == approved['manifest_bytes'],
             '此CPU或显卡模型尚未纳入已核对的开源参考包。')
    doc = _json(raw)
    validate_source_identity(doc, approved)
    draws, triangles = approved['draws'], approved['triangles']
    _require(doc.get('physical_draws') == draws and doc.get('triangles') == triangles
             and len(doc.get('draws', ())) == draws and len(doc.get('parts', ())) == draws,
             '开源硬件部件或几何数量不一致。')
    packed = verify_files(package, approved['asset'])
    _require(type(packed) is bytes and len(packed) == triangles * 72, '开源硬件需保留完整不可变几何缓冲。')
    from assembly_geometry import Mesh, Scene
    part_index = {part['id']: part for part in doc['parts']}
    _require(len(part_index) == draws and all(identity.startswith('reference:') for identity in part_index),
             '开源硬件部件标识无效。')
    cursor, meshes = 0, []
    for row in doc['draws']:
        length, count, start = row.get('bytes'), row.get('vertex_count'), row.get('offset')
        _require(type(length) is int and type(count) is int and type(start) is int
                 and start == cursor and count > 0 and count % 3 == 0
                 and length == count * 24 and start + length <= len(packed), '开源硬件几何范围无效。')
        identity = row['part_id']
        _require(identity in part_index and row['component'] == approved['asset'] == part_index[identity]['kind'],
                 '开源硬件几何与部件不匹配。')
        view = memoryview(packed)[cursor:cursor + length].cast('f')
        _require(view.readonly and view.obj is packed and all(math.isfinite(v) for v in view), '开源硬件含无效坐标。')
        rgba = row['source_RGBA_linear']
        meshes.append(Mesh(row['name'], view, _srgb(rgba[:3], rgba[3]), component=row['component'], part_id=identity))
        cursor += length
    _require(cursor == len(packed) and sum(mesh.vertex_count for mesh in meshes) // 3 == triangles,
             '开源硬件缓冲覆盖不完整。')
    low = tuple(min(min(mesh.vertices[a::6]) for mesh in meshes) for a in range(3))
    high = tuple(max(max(mesh.vertices[a::6]) for mesh in meshes) for a in range(3))
    _require(list(low) == doc['reference_bounds']['minimum'] and list(high) == doc['reference_bounds']['maximum'],
             '开源硬件范围与核对记录不一致。')
    metadata = dict(reference_only=True, reference_model_id=doc['model_id'], visual_style='miniature',
                    source_license='CC-BY-4.0', source_url=approved['source_url'],
                    reference_bounds=dict(minimum=low, maximum=high), hardware=dict(parts=doc['parts']),
                    dimensions_verified=False, mechanical_fit_verified=False, telemetry_bound=False,
                    source_quality_accepted=False, cooling=dict(cpu_fan_tach_usable=False, real_cpu_rotor_parts=()),
                    source_materials=doc['source_materials'], changes=doc['changes'],
                    source_parent_metadata_sha256=approved['parent_sha256'], source_lod_indices_sha256=approved['lod_sha256'],
                    coordinate_convention=doc['coordinate_convention'], material_limit=doc['runtime_material_limit'])
    scene = Scene(tuple(meshes), tuple(max(.01, b-a) for a, b in zip(low, high)), metadata)
    limits = (doc['changes'], doc['runtime_material_limit'],
              '源比例未经制造尺寸校准；独立检视不自动装机，不代表本机型号、安装兼容性或实测转速。')
    return ReferenceModel(doc['model_id'], doc['label'], scene,
                          tuple(MappingProxyType(dict(part)) for part in doc['parts']),
                          approved['attribution'], tuple(doc['source_urls']), limits, len(packed),
                          approved['source_sha256'], ('',) * draws)
