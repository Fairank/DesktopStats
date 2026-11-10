"""Explicit, bounded use of reviewed open hardware models in the native viewer.

No directory discovery, profile, sensor, timer, Qt or decoder process is used.
Original adapter code follows this project's LICENSE; the source model data
remains MIT, copyright Yoseph / Three.js authors / Canvas contributors. No
project noncommercial restriction or ownership watermark is applied to it.
"""
from array import array
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import sys
from types import MappingProxyType
import zipfile


STYLES = ('miniature', 'cartoon', 'notebook_color', 'notebook_line', 'sticker', 'papercut')
MAX_PACKAGE_BYTES = 12 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_MEMBERS = 64
MAX_TRIANGLES = 100000
SOURCE_URL = 'https://github.com/Yoosseph/pc-anatomy/tree/9ca9c9635a19abd189cd9978396d26be7a5d0858'
FAN_SHA = '8ba69755544be96e31311cb7f617d147b5bde4796346ffb2d00fe77120ec3009'
LICENSES = {
    'LICENSE-PC-ANATOMY.txt': '84ebe56c16f78183e3c5014e5f47e01a9e211a229ac022550e255fa4ab2e383b',
    'LICENSE-THREE.txt': '4c40a1ef62450b857c3b2aaf294936304cd552d965fbcd9d32d4c5bcf4ba4454',
    'LICENSE-CANVAS.txt': '8802fecf9da4367bc23bcf20b21cc143785fc6c92b152f3fa7fbe6ce08d344d6',
}
# The document itself is pinned before JSON is interpreted. A self-supplied
# manifest cannot turn an arbitrary downloaded model into a reviewed asset.
APPROVED_COMPONENTS = {
    'a5b54b5fc6b63ba1cf120b5b687cccbf5dd17ed67de74f300c5cd286d1b26f75':
        ('pc-anatomy-air-cooler', '风冷散热器 · 开源结构参考', 11, 103, 111, 16312),
    'b9765577287fd1602da8bc6d6e0acd333979544a1ec5c2c946fbfbb74f6c993a':
        ('pc-anatomy-aio-cooler', '一体水冷 · 开源结构参考', 14, 187, 211, 37774),
    '56e3ffa2127ddd5a416ae4aeb173891e10e4093dad61e99c6834e43486398092':
        ('pc-anatomy-air-cooler-normal054', '风冷散热器 · 开源结构参考', 11, 103, 111, 16312),
    '8d47e1d8461d999c2a80a553ec7f77a2601c5062ac8cff7eb144a90c2301d5b7':
        ('pc-anatomy-aio-normal054', '一体水冷 · 开源结构参考', 14, 187, 211, 37774),
}
_LABELS = {
    'frame': '风扇框架', 'impeller': '叶轮与轮毂',
    'coolerbase': '冷板与底座', 'coolerpaste': '导热层', 'coolerpipes': '热管',
    'coolerfins': '散热鳍片', 'coolercap': '顶盖', 'coolerfan': '散热风扇',
    'coolerclip': '风扇卡扣', 'coolermount': '安装扣具',
    'aioradiator': '冷排', 'aiofans': '冷排风扇', 'aiopump': '泵体',
    'aioimpeller': '水泵叶轮', 'aiocoldplate': '冷板与微鳍片',
    'aiotubes': '水管', 'aiocoolant': '内部冷却液', 'aiofittings': '接头',
}
_MATERIAL_LIMITS = (
    '开源教学结构参考；并非经厂商核准的零售型号、制造尺寸或安装保证。',
    '当前检视使用原几何和颜色因子；贴图、灯光传输和完整PBR未在此检视中还原。',
    '教育文字平面和非实体光源保留在文件中，以部件列表替代画面文字；实体部件不删减。',
    '未绑定本机温度或转速，叶轮保持静止；不把参考动作当成实测或真实拆装。',
)


class ModelError(ValueError):
    """A selected package cannot be used as this reviewed reference."""


@dataclass(frozen=True)
class ReferenceModel:
    model_id: str
    label: str
    scene: object
    parts: tuple
    attribution: str
    source_urls: tuple
    material_limits: tuple
    geometry_bytes: int
    source_sha256: str
    _roles: tuple = ()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ModelError('模型中的计数或范围无效。')
    return value


def _safe_name(name):
    if (type(name) is not str or not name or len(name) > 180
            or not re.fullmatch(r'[A-Za-z0-9_./-]+', name)
            or name.startswith('/') or any(p in ('', '.', '..') or p.endswith('.')
                                          for p in name.split('/'))):
        raise ModelError('模型包包含不安全的文件路径。')
    return name


def _json(raw):
    if not 0 < len(raw) <= MAX_DOCUMENT_BYTES:
        raise ModelError('模型说明文件超过限制。')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ModelError('模型说明包含重复字段。')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ModelError('非有限数值。')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ModelError('模型说明文件无法读取。') from error


class _Package:
    """One selected directory or ZIP. Never extracts or follows a member link."""
    def __init__(self, path):
        self.path = Path(path)
        self.archive = None
        self.files = None
        self.total_read = 0
        if self.path.is_dir():
            self.base = self.path.resolve(strict=True)
        elif self.path.is_file() and self.path.suffix.casefold() == '.zip':
            if self.path.is_symlink() or not 0 < self.path.stat().st_size <= MAX_PACKAGE_BYTES:
                raise ModelError('所选模型包过大或为链接。')
            try:
                self.archive = zipfile.ZipFile(self.path)
                infos = self.archive.infolist()
                if len(infos) > MAX_MEMBERS:
                    raise ModelError('模型包文件数量过多。')
                self.files = {}
                total = 0
                folded = set()
                for info in infos:
                    if info.is_dir():
                        _safe_name(info.filename.rstrip('/'))
                        continue
                    name = _safe_name(info.filename)
                    if (name.casefold() in folded or info.flag_bits & 1
                            or stat.S_ISLNK(info.external_attr >> 16)
                            or not 0 <= info.file_size <= MAX_FILE_BYTES):
                        raise ModelError('模型包含重复、链接、加密或过大的文件。')
                    folded.add(name.casefold())
                    total += info.file_size
                    if total > MAX_PACKAGE_BYTES:
                        raise ModelError('模型包解压后超过限制。')
                    self.files[name] = info
            except BaseException:
                self.close()
                raise
        else:
            raise ModelError('请选择已下载的模型ZIP或其解压目录。')

    def exists(self, name):
        _safe_name(name)
        if self.archive is not None:
            return name in self.files
        return (self.base / name).is_file()

    def read(self, name, cap=MAX_FILE_BYTES):
        _safe_name(name)
        if self.archive is not None:
            info = self.files.get(name)
            if info is None or info.file_size > cap:
                raise ModelError('模型包缺少文件或文件过大：' + name)
            with self.archive.open(info) as stream:
                raw = stream.read(cap + 1)
            if len(raw) != info.file_size or len(raw) > cap:
                raise ModelError('模型包文件长度不一致。')
        else:
            current = self.base
            for component in PurePosixPath(name).parts:
                current = current / component
                info = current.lstat()
                if (stat.S_ISLNK(info.st_mode)
                        or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
                    raise ModelError('模型路径包含链接或重解析点。')
            if not current.resolve(strict=True).is_relative_to(self.base) or not current.is_file():
                raise ModelError('模型文件位于所选目录之外。')
            size = current.stat().st_size
            if not 0 <= size <= cap:
                raise ModelError('模型文件超过限制。')
            with current.open('rb') as stream:
                raw = stream.read(cap + 1)
            if len(raw) != size:
                raise ModelError('模型文件在读取时发生变化。')
        self.total_read += len(raw)
        if self.total_read > MAX_PACKAGE_BYTES:
            raise ModelError('本次模型读取超过限制。')
        return raw

    def verify(self, name, size, checksum):
        raw = self.read(name, _integer(size, 0, MAX_FILE_BYTES))
        if len(raw) != size or _sha(raw) != checksum:
            raise ModelError('模型文件校验不匹配：' + name)
        return raw

    def notices(self, prefix='', canvas=False):
        for name in tuple(LICENSES)[:3 if canvas else 2]:
            raw = self.read(prefix + name, 4096)
            if _sha(raw) != LICENSES[name]:
                raise ModelError('模型原始许可缺失或被更改：' + name)

    def close(self):
        if self.archive is not None:
            self.archive.close()
            self.archive = None


_IDENTITY = (1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.)


def _matrix(values):
    if (not isinstance(values, (tuple, list)) or len(values) != 16
            or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 10000 for v in values)
            or tuple(values[i] for i in (3, 7, 11, 15)) != (0, 0, 0, 1)):
        raise ModelError('模型变换矩阵无效。')
    return tuple(values)


def _multiply(a, b):
    return tuple(sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4))
                 for c in range(4) for r in range(4))


def _normal_basis(m):
    a, b, c, d, e, f, g, h, i = (m[n] for n in (0, 4, 8, 1, 5, 9, 2, 6, 10))
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if not math.isfinite(det) or abs(det) < 1e-12:
        raise ModelError('模型包含不可逆变换。')
    return tuple(v / det for v in (e*i-f*h, f*g-d*i, d*h-e*g,
                                  c*h-b*i, a*i-c*g, b*g-a*h,
                                  b*f-c*e, c*d-a*f, a*e-b*d))


def _expanded(positions, normals, indices, matrix, unit):
    """Legacy draw adapter, packed once. No Python float tuple is retained."""
    count = len(positions) // 3
    if count == 0 or len(normals) != count * 3 or len(indices) % 3:
        raise ModelError('模型顶点或法线数量不一致。')
    basis = _normal_basis(matrix)
    vertices = array('f')
    for n in range(count):
        x, y, z = positions[n*3:n*3+3]
        nx, ny, nz = normals[n*3:n*3+3]
        point = ((matrix[0]*x+matrix[4]*y+matrix[8]*z+matrix[12])*unit,
                 (matrix[1]*x+matrix[5]*y+matrix[9]*z+matrix[13])*unit,
                 (matrix[2]*x+matrix[6]*y+matrix[10]*z+matrix[14])*unit)
        normal = (basis[0]*nx+basis[1]*ny+basis[2]*nz,
                  basis[3]*nx+basis[4]*ny+basis[5]*nz,
                  basis[6]*nx+basis[7]*ny+basis[8]*nz)
        length = math.hypot(*normal)
        if (not all(math.isfinite(v) and abs(v) <= 100000 for v in point)
                or not math.isfinite(length) or length < 1e-12):
            raise ModelError('模型含非有限坐标或无效法线。')
        vertices.extend((*point, *(v / length for v in normal)))
    out = array('f')
    for index in indices:
        if not 0 <= index < count:
            raise ModelError('模型索引位于顶点范围之外。')
        out.extend(vertices[index*6:index*6+6])
    return memoryview(out.tobytes()).cast('f')


def _srgb(color, alpha=1.):
    if (not isinstance(color, (tuple, list)) or len(color) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in color)
            or type(alpha) not in (int, float) or not math.isfinite(alpha) or not 0 <= alpha <= 1):
        raise ModelError('模型颜色无效。')
    return tuple(12.92*v if v <= .0031308 else 1.055*v**(1/2.4)-.055 for v in color) + (alpha,)


def _finish(identity, label, meshes, parts, checksum, roles=(), canvas=True):
    from assembly_geometry import Scene
    if not meshes or len(meshes) > 512 or sum(m.vertex_count for m in meshes) // 3 > MAX_TRIANGLES:
        raise ModelError('模型网格数量或三角形数量超过限制。')
    low = tuple(min(min(m.vertices[axis::6]) for m in meshes) for axis in range(3))
    high = tuple(max(max(m.vertices[axis::6]) for m in meshes) for axis in range(3))
    immutable_parts = tuple(MappingProxyType(dict(row)) for row in parts)
    metadata = dict(reference_only=True, reference_model_id=identity,
                    visual_style='miniature', dimensions_verified=False,
                    mechanical_fit_verified=False, telemetry_bound=False,
                    reference_bounds=dict(minimum=low, maximum=high),
                    hardware=dict(parts=[dict(row) for row in parts]),
                    cooling=dict(cpu_fan_tach_usable=False, real_cpu_rotor_parts=()),
                    source_url=SOURCE_URL, source_license='MIT',
                    annotation_rendering='part_list_only', source_quality_accepted=False)
    scene = Scene(tuple(meshes), tuple(max(.01, b-a) for a, b in zip(low, high)), metadata)
    attribution = 'PC Anatomy © 2026 Yoseph · MIT；Three.js MIT' + ('；Canvas MIT' if canvas else '')
    return ReferenceModel(identity, label, scene, immutable_parts, attribution,
                          (SOURCE_URL,), _MATERIAL_LIMITS,
                          sum(m.vertices.nbytes for m in meshes), checksum, tuple(roles))


def _span(binary, row, width, component=5126):
    code, size = {5121: ('B', 1), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}[component]
    start = _integer(row.get('offset'), 0, len(binary))
    count = _integer(row.get('count'), 1, 300000)
    length = _integer(row.get('bytes'), 1, len(binary))
    if (row.get('componentType') != component or start % size
            or length != count * width * size or start + length > len(binary)):
        raise ModelError('模型属性缓冲区范围无效。')
    raw = memoryview(binary)[start:start+length]
    if _sha(raw) != row.get('sha256'):
        raise ModelError('模型属性缓冲区校验不匹配。')
    return raw.cast(code)


def _component(package, raw):
    checksum = _sha(raw)
    descriptor = APPROVED_COMPONENTS.get(checksum)
    if descriptor is None:
        raise ModelError('此结构模型尚未纳入已核对的开源参考包。')
    identity, label, unit, physical_count, draw_count, triangles = descriptor
    doc = _json(raw)
    if (doc.get('format') != 'DesktopStats.pc-anatomy-source-component.053.2'
            or doc['source']['source_unit_mm'] != unit
            or doc['source']['commit'] != SOURCE_URL.rsplit('/', 1)[1]):
        raise ModelError('模型来源或单位与核对记录不一致。')
    package.notices(canvas=True)
    asset = doc['asset']
    binary = package.verify(asset['geometry_file'], asset['geometry_bytes'], asset['geometry_sha256'])
    instances = package.verify(asset['instance_file'], asset['instance_bytes'], asset['instance_sha256'])
    for texture in doc.get('textures', ()):
        for prefix in ('png', 'rgba'):
            package.verify(texture[prefix+'_file'], texture[prefix+'_bytes'], texture[prefix+'_sha256'])
    pieces = {p['key']: p for p in asset['source_pieces']}
    if len(pieces) != 8:
        raise ModelError('模型独立部件数量不一致。')
    from assembly_geometry import Mesh
    meshes = []
    roles = []
    cached = {}
    families = {}
    selected_nodes = 0
    nodes = doc['nodes']
    if not isinstance(nodes, list) or len(nodes) > 512:
        raise ModelError('模型节点数量超过限制。')
    for n, node in enumerate(nodes):
        if node['id'] != n or (node['parent'] is not None and not 0 <= node['parent'] < n):
            raise ModelError('模型节点层级无效。')
        family = node.get('source_piece_key', families.get(node['parent']))
        families[n] = family
        if 'geometry' not in node or node.get('annotation'):
            continue
        if node.get('role') != 'physical' or family not in pieces:
            raise ModelError('模型实体部件归属无效。')
        selected_nodes += 1
        gid = _integer(node['geometry'], 0, len(doc['geometries']) - 1)
        geometry = doc['geometries'][gid]
        if gid not in cached:
            attributes = geometry['attributes']
            p = _span(binary, attributes['position'], 3)
            normal = _span(binary, attributes['normal'], 3)
            index = geometry['index']
            ct = index['componentType']
            if ct not in (5121, 5123, 5125):
                raise ModelError('模型索引类型不支持。')
            cached[gid] = (p, normal, _span(binary, index, 1, ct))
        p, normal, indices = cached[gid]
        world = _matrix(node['world_matrix'])
        poses = (world,)
        if 'instances' in node:
            item = node['instances']
            count = _integer(item['count'], 1, 64)
            start = _integer(item['offset'], 0, len(instances))
            length = count * 64
            block = memoryview(instances)[start:start+length]
            if (item['bytes'] != length or len(block) != length
                    or _sha(block) != item['sha256']):
                raise ModelError('模型实例矩阵校验不匹配。')
            poses = tuple(_multiply(world, _matrix(matrix)) for matrix in struct.iter_unpack('<16f', block))
        material = doc['materials'][_integer(node['material'], 0, len(doc['materials']) - 1)]
        tone = _srgb(material['color'], material['opacity'])
        kind = 'fans' if pieces[family]['concept'] in ('coolerfan', 'aiofans') else 'cooler'
        role = 'blade' if kind == 'fans' and 'instances' in node else ''
        for instance, pose in enumerate(poses):
            vertices = _expanded(p, normal, indices, pose, unit)
            meshes.append(Mesh('reference:'+family+':'+str(n)+':'+str(instance), vertices,
                               tone, component=kind, part_id='reference:'+family))
            roles.append(role)
    if (selected_nodes != physical_count or len(meshes) != draw_count
            or sum(m.vertex_count for m in meshes) // 3 != triangles):
        raise ModelError('模型实体结构与已核对记录不一致。')
    parts = [dict(id='reference:'+key, label=_LABELS.get(p['concept'], p['concept']),
                  kind='fans' if p['concept'] in ('coolerfan', 'aiofans') else 'cooler')
             for key, p in pieces.items()]
    return _finish(identity, label, meshes, parts, checksum, roles)


def _local_matrix(node):
    if 'matrix' in node:
        return _matrix(node['matrix'])
    tx, ty, tz = node.get('translation', (0., 0., 0.))
    sx, sy, sz = node.get('scale', (1., 1., 1.))
    x, y, z, w = node.get('rotation', (0., 0., 0., 1.))
    return _matrix(((1-2*(y*y+z*z))*sx, 2*(x*y+z*w)*sx, 2*(x*z-y*w)*sx, 0,
                    2*(x*y-z*w)*sy, (1-2*(x*x+z*z))*sy, 2*(y*z+x*w)*sy, 0,
                    2*(x*z+y*w)*sz, 2*(y*z-x*w)*sz, (1-2*(x*x+y*y))*sz, 0,
                    tx, ty, tz, 1))


def _fan(package):
    raw = package.verify('models/generic-fan-derived.glb', 316540, FAN_SHA)
    package.notices('licenses/')
    if struct.unpack_from('<III', raw) != (0x46546c67, 2, len(raw)):
        raise ModelError('GLB头无效。')
    length, kind = struct.unpack_from('<II', raw, 12)
    if kind != 0x4e4f534a or not 0 < length <= 65536:
        raise ModelError('GLB说明块无效。')
    doc = _json(raw[20:20+length])
    offset = 20 + length
    n, kind = struct.unpack_from('<II', raw, offset)
    if kind != 0x004e4942 or offset+8+n != len(raw):
        raise ModelError('GLB数据块无效。')
    binary = memoryview(raw)[offset+8:]
    def accessor(identity, width, component):
        a = doc['accessors'][_integer(identity, 0, len(doc['accessors'])-1)]
        v = doc['bufferViews'][a['bufferView']]
        code, size = {5121: ('B',1), 5123: ('H',2), 5125: ('I',4), 5126: ('f',4)}[component]
        start = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        count = a['count']
        if (a['componentType'] != component or v.get('buffer', 0) != 0
                or v.get('byteStride') or a.get('sparse') or a.get('normalized')
                or v['byteLength'] != count*width*size or start+count*width*size > len(binary)):
            raise ModelError('GLB属性格式不支持。')
        return binary[start:start+count*width*size].cast(code)
    nodes = doc['nodes']
    if len(nodes) != 21 or len(doc['meshes']) != 6:
        raise ModelError('风扇节点数量不一致。')
    parents = {}
    for n, node in enumerate(nodes):
        for child in node.get('children', ()):
            if child in parents or type(child) is not int or not 0 <= child < len(nodes):
                raise ModelError('风扇层级无效。')
            parents[child] = n
    worlds = {}
    families = {}
    visiting = set()
    def world(n):
        if n in worlds:
            return worlds[n]
        if n in visiting:
            raise ModelError('风扇层级包含循环。')
        visiting.add(n)
        parent = parents.get(n)
        if n != 0 and parent is None or n == 0 and parent is not None:
            raise ModelError('风扇节点不属于原始场景。')
        matrix = _multiply(world(parent), _local_matrix(nodes[n])) if parent is not None else _local_matrix(nodes[n])
        family = nodes[n].get('name')
        families[n] = family if family in ('frame', 'impeller') else families.get(parent)
        worlds[n] = matrix
        visiting.remove(n)
        return matrix
    meshes = []
    roles = []
    from assembly_geometry import Mesh
    for n, node in enumerate(nodes):
        world(n)
        if 'mesh' not in node:
            continue
        gid = node['mesh']
        primitive, = doc['meshes'][gid]['primitives']
        p = accessor(primitive['attributes']['POSITION'], 3, 5126)
        normal = accessor(primitive['attributes']['NORMAL'], 3, 5126)
        index = primitive['indices']
        ct = doc['accessors'][index]['componentType']
        indices = accessor(index, 1, ct)
        family = families[n]
        if family not in ('frame', 'impeller'):
            raise ModelError('风扇部件归属无效。')
        material = doc['materials'][primitive['material']]['pbrMetallicRoughness']
        color = material.get('baseColorFactor', [1, 1, 1, 1])
        meshes.append(Mesh('reference:fan:'+str(n), _expanded(p, normal, indices, worlds[n], 1000),
                           _srgb(color[:3], color[3]), component='fans', part_id='reference:'+family))
        roles.append('blade' if gid == 4 else 'cap' if gid == 2 else '')
    if len(meshes) != 17 or sum(m.vertex_count for m in meshes)//3 != 7090:
        raise ModelError('风扇实体结构不一致。')
    parts = [dict(id='reference:'+key, label=_LABELS[key], kind='fans') for key in ('frame', 'impeller')]
    return _finish('pc-anatomy-generic-fan', '独立风扇 · 开源结构参考', meshes, parts, FAN_SHA, roles, canvas=False)


def load_reference(path):
    """Load exactly one user-selected reviewed ZIP or directory, never install it."""
    if sys.byteorder != 'little':
        raise ModelError('当前模型适配需要小端系统。')
    package = None
    try:
        package = _Package(path)
        if package.exists('component053.json'):
            return _component(package, package.read('component053.json', MAX_DOCUMENT_BYTES))
        if package.exists('models/generic-fan-derived.glb'):
            return _fan(package)
        raise ModelError('未找到支持的开源参考模型；请选择对应完整模型包。')
    except ModelError:
        raise
    except (zipfile.BadZipFile, KeyError, IndexError, struct.error, TypeError, OverflowError) as error:
        raise ModelError('所选模型包格式不完整或不受支持。') from error
    finally:
        if package is not None:
            package.close()


def scene_for_style(model, style):
    """Change illustration colors; retain the exact same immutable PN owners."""
    from assembly_geometry import Scene
    from assembly_style import paint_color
    from top_bar_config import HARDWARE_ICON_STYLES
    if not isinstance(model, ReferenceModel) or style not in HARDWARE_ICON_STYLES:
        raise ModelError('请选择已有的硬件外观。')
    if style == 'miniature':
        return model.scene
    meshes = []
    for n, mesh in enumerate(model.scene.meshes):
        source = mesh.color
        role = model._roles[n] if n < len(model._roles) else ''
        target = (.82 if style == 'sticker' else .54) if role == 'blade' else .82 if role == 'cap' and style == 'papercut' else None
        if target is not None and style in ('cartoon', 'notebook_color', 'sticker', 'papercut'):
            light = sum(v*w for v, w in zip(source[:3], (.2126, .7152, .0722)))
            if light < target:
                mix = (target-light)/(1-light)
                source = tuple(v*(1-mix)+mix for v in source[:3])+(source[3],)
        meshes.append(replace(mesh, color=paint_color(source, style, mesh.component)))
    metadata = dict(model.scene.metadata, visual_style=style)
    return Scene(tuple(meshes), model.scene.dimensions, metadata)
