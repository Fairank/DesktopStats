"""Bounded data-only hardware packs. No Qt, network, watcher, or import-time IO.

Version 1 accepts CPU packages rendered by the app's shared generators. Archives
are never extracted or executed. Only small picker/identity indexes remain in
memory; at most eight selected model records are retained. Future model kinds
need an explicit schema and renderer contract, not executable plugins.
"""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import zipfile
import zlib
from urllib.parse import urlsplit

FORMAT = 1
MAX_PACKS = 16
MAX_PRODUCTS = 256
MAX_TOTAL_PRODUCTS = 1024
MAX_ARCHIVE_BYTES = 1536 * 1024
MAX_MANIFEST_BYTES = 256 * 1024
MAX_MODELS_BYTES = 1024 * 1024
SELECTED_CACHE_LIMIT = 8
PACK_RELEASE_URL = 'https://github.com/Fairank/DesktopStats/releases'
LICENSE = 'PolyForm-Noncommercial-1.0.0'
LICENSE_SHA256 = 'ffcca38841adb694b6f380647e15f17c446a4d1656fed51a1e2041d064c94cc8'
_ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z', re.ASCII)
_VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+\Z', re.ASCII)
_FAMILIES = {
    'intel_lga115x_1200': ('intel', 'intel_square', 'lga'),
    'intel_lga1700_1851': ('intel', 'intel_rectangle', 'lga'),
    'intel_lga2011_2066': ('intel', 'intel_hedt', 'lga'),
    'amd_am4': ('amd', 'amd_am4', 'pga'),
    'amd_am5': ('amd', 'amd_am5_notched', 'lga'),
    'amd_tr4_family': ('amd', 'amd_threadripper', 'lga'),
    'amd_str5': ('amd', 'amd_threadripper', 'lga'),
}
_BASE_IDS = frozenset(('intel-13700kf', 'amd-9950x', 'amd-7800x3d'))


class PackError(ValueError):
    """A rejected pack never replaces the last valid installed archive."""


def _identifier(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64 or not _ID.fullmatch(value):
        raise PackError('Invalid identifier')
    return value


def _string(value, limit=256):
    if (not isinstance(value, str) or not value or len(value) > limit
            or any(ord(c) < 32 or c in '<>' for c in value)):
        raise PackError('Invalid text')
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackError('Duplicate JSON field')
        result[key] = value
    return result


def _json(raw):
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(PackError('Non-finite number')))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise PackError('Invalid bounded JSON') from error


def _keys(row, required, optional=()):
    if not isinstance(row, dict) or not set(required) <= row.keys() or row.keys() - set(required) - set(optional):
        raise PackError('Unsupported model fields')


def _urls(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 8:
        raise PackError('Missing source URLs')
    for value in values:
        _string(value, 1024)
        try:
            url = getattr(urlsplit,'__wrapped__',urlsplit)(value)
            if url.scheme != 'https' or not url.hostname or url.username or url.password:
                raise PackError('Invalid source URL')
        except ValueError as error:
            raise PackError('Invalid source URL') from error
    return list(values)


def _summary(row):
    _keys(row, ('id', 'label', 'vendor', 'series', 'aliases'))
    _identifier(row['id']); _string(row['label']); _string(row['series'], 80)
    if row['id'] in _BASE_IDS or row['vendor'] not in ('intel', 'amd'):
        raise PackError('Reserved CPU identity or unsupported vendor')
    aliases = row['aliases']
    if not isinstance(aliases, list) or not 1 <= len(aliases) <= 8:
        raise PackError('Invalid aliases')
    for alias in aliases:
        _string(alias)
    if len(set(aliases)) != len(aliases):
        raise PackError('Duplicate aliases')
    return deepcopy(row)


def validate_cpu(row):
    """Validate the entire renderer boundary, including null/unknown mechanics."""
    _keys(row, ('id', 'label', 'vendor', 'series', 'aliases', 'sources', 'cpu_package'))
    result = _summary({key: row[key] for key in ('id', 'label', 'vendor', 'series', 'aliases')})
    result['sources'] = _urls(row['sources'])
    package = row['cpu_package']
    required = ('id', 'model_id', 'vendor', 'socket', 'width_mm', 'length_mm', 'substrate_mm', 'ihs_kind',
                'contacts', 'pin_count', 'notch_profile', 'label_ascii', 'status', 'source_urls')
    _keys(package, required, ('topology_map_verified', 'internal_layout_verified', 'cooler_inferred',
                              'package_family','dimensions_status','topology_status'))
    family = package.get('package_family', package['id'])
    if not isinstance(family,str) or family not in _FAMILIES or package['id'] != family:
        raise PackError('Unknown CPU generator')
    vendor, ihs, contacts = _FAMILIES[family]
    if (result['vendor'] != vendor or package['vendor'] != vendor or package['model_id'] != result['id']
            or package['ihs_kind'] != ihs or package['contacts'] != contacts):
        raise PackError('Conflicting CPU package')
    _string(package['socket'], 24)
    allowed_sockets = {
        'intel_lga115x_1200': {'LGA1150', 'LGA1151', 'LGA1155', 'LGA1156', 'LGA1200'},
        'intel_lga1700_1851': {'LGA1700', 'LGA1851'},
        'intel_lga2011_2066': {'LGA2011', 'LGA2011-3', 'LGA2066'},
        'amd_am4': {'AM4'}, 'amd_am5': {'AM5'},
        'amd_tr4_family': {'TR4', 'sTR4', 'sTRX4', 'sWRX8'}, 'amd_str5': {'sTR5'},
    }
    if package['socket'] not in allowed_sockets[family]:
        raise PackError('Socket does not match generator')
    for key in ('width_mm', 'length_mm', 'substrate_mm'):
        value = package[key]
        if value is not None and (type(value) not in (int, float) or type(value) is float and not math.isfinite(value)
                                  or not ((.3 <= value <= 4) if key == 'substrate_mm' else (20 <= value <= 90))):
            raise PackError('CPU dimensions exceed renderer limits')
    if (package['width_mm'] is None) != (package['length_mm'] is None):
        raise PackError('Partial CPU envelope')
    pins = package['pin_count']
    if pins is not None and (type(pins) is not int or not 1 <= pins <= 8192):
        raise PackError('CPU contact count exceeds renderer limits')
    notch = 'threadripper_carrier' if ihs == 'amd_threadripper' else ihs
    if package['notch_profile'] != notch:
        raise PackError('Unsupported notch profile')
    if not isinstance(package['label_ascii'], str) or not re.fullmatch(r'[A-Z0-9 -]{1,28}', package['label_ascii']):
        raise PackError('Invalid CPU marking')
    # Review status is descriptive evidence, never permission to load code/CAD
    # or to infer electrical topology and sensor/rotor bindings.
    if package['status'] not in ('reviewed', 'unverified_reference'):
        raise PackError('Unsupported CPU evidence state')
    if package.get('dimensions_status','unverified_reference') not in ('primary_verified','unverified_reference'):
        raise PackError('Unsupported dimensional evidence')
    if package.get('topology_status','unverified_reference') not in ('interface_verified','unverified_reference'):
        raise PackError('Unsupported topology evidence')
    for key in ('topology_map_verified', 'internal_layout_verified', 'cooler_inferred'):
        if package.get(key, False) is not False:
            raise PackError('Unsupported hardware inference')
    if _urls(package['source_urls']) != row['sources']:
        raise PackError('Conflicting source declarations')
    result['cpu_package'] = deepcopy(package)
    return result


def _archive(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_ARCHIVE_BYTES:
        raise PackError('Pack size exceeds limit')
    try:
        with zipfile.ZipFile(io.BytesIO(raw),metadata_encoding='utf-8') as archive:
            members = archive.infolist()
            if len(members) != 2 or {row.filename for row in members} != {'manifest.json', 'models.json'}:
                raise PackError('Pack must contain only manifest.json and models.json')
            for row in members:
                limit = MAX_MANIFEST_BYTES if row.filename == 'manifest.json' else MAX_MODELS_BYTES
                mode = row.external_attr >> 16
                if (row.file_size > limit or row.file_size < 1 or row.flag_bits & 1
                        or stat.S_ISLNK(mode) or row.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise PackError('Unsupported archive entry')
            manifest_raw = archive.read('manifest.json')
            model_raw = archive.read('models.json')
    except (zipfile.BadZipFile, OSError, RuntimeError, EOFError,UnicodeError,NotImplementedError,zlib.error) as error:
        raise PackError('Unreadable pack') from error
    manifest = _json(manifest_raw)
    _keys(manifest, ('format', 'id', 'version', 'kind', 'label', 'license', 'license_text', 'notice', 'models_sha256', 'models_bytes', 'products'))
    if type(manifest['format']) is not int or manifest['format'] != FORMAT or manifest['kind'] != 'cpu':
        raise PackError('Unsupported pack format or hardware kind')
    _identifier(manifest['id']); _string(manifest['label'], 120)
    if not isinstance(manifest['version'], str) or len(manifest['version'])>32 or not _VERSION.fullmatch(manifest['version']):
        raise PackError('Invalid pack version')
    if manifest['license'] != LICENSE:
        raise PackError('Unsupported pack license')
    license_text=manifest['license_text']
    if (not isinstance(license_text,str) or len(license_text)>20000
            or hashlib.sha256(license_text.encode('utf-8')).hexdigest()!=LICENSE_SHA256):
        raise PackError('Missing complete noncommercial license')
    _string(manifest['notice'],512)
    if (type(manifest['models_bytes']) is not int or manifest['models_bytes'] != len(model_raw)
            or manifest['models_sha256'] != hashlib.sha256(model_raw).hexdigest()):
        raise PackError('Pack content checksum mismatch')
    products = manifest['products']
    if not isinstance(products, list) or not 1 <= len(products) <= MAX_PRODUCTS:
        raise PackError('Product count exceeds limit')
    products = [_summary(row) for row in products]
    if len({row['id'] for row in products}) != len(products):
        raise PackError('Duplicate CPU identity')
    models = _json(model_raw)
    if not isinstance(models, list) or len(models) != len(products):
        raise PackError('Pack inventory does not match manifest')
    models = [validate_cpu(row) for row in models]
    if [{key: row[key] for key in ('id', 'label', 'vendor', 'series', 'aliases')} for row in models] != products:
        raise PackError('Pack identity index does not match models')
    return manifest, models


def make_pack(pack_id, label, models, version='1.0.0'):
    """Authoring helper; deterministic archive, validated by the runtime reader."""
    encoded = (json.dumps(models, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    manifest = dict(format=FORMAT, id=pack_id, version=version, kind='cpu', label=label,
                    license=LICENSE, license_text=Path(__file__).with_name('LICENSE').read_bytes().decode('utf-8'),
                    notice='Original procedural model data: DesktopStats contributors. Product names and trademarks belong to their respective owners.',
                    models_sha256=hashlib.sha256(encoded).hexdigest(), models_bytes=len(encoded),
                    products=[{key: row[key] for key in ('id', 'label', 'vendor', 'series', 'aliases')} for row in models])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in (('manifest.json', (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')),
                              ('models.json', encoded)):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compresslevel=9)
    raw = buffer.getvalue()
    _archive(raw)
    return raw


def _read_regular(path, limit=MAX_ARCHIVE_BYTES):
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_size > limit:
            raise PackError('Pack must be a bounded regular file')
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            if (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
                raise PackError('Pack changed before reading')
            raw = stream.read(limit + 1)
        after = path.lstat()
        if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise PackError('Pack changed while reading')
        if len(raw) > limit:
            raise PackError('Pack size exceeds limit')
        return raw
    except OSError as error:
        raise PackError('Cannot read pack') from error


class PackStore:
    """One profile, explicit reload/install/remove; no polling or permanent handles."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self._indexes = {}
        self._selected = OrderedDict()
        self._loaded = False
        self.generation = 0
        self._directory_identity = None
        self.errors = ()

    def _assert_directory(self):
        try:
            info=self.directory.lstat()
            identity=(info.st_dev,info.st_ino)
            if (not stat.S_ISDIR(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400
                    or self._directory_identity is not None and identity!=self._directory_identity):
                raise PackError('Pack directory changed or was redirected')
            return identity
        except OSError as error:
            raise PackError('Pack directory unavailable') from error

    def reload(self):
        self.generation += 1
        self._indexes.clear(); self._selected.clear()
        self._directory_identity=None
        errors = []; total = 0
        try:
            if not self.directory.exists():
                self._loaded = True; self.errors = (); return
            self._directory_identity=self._assert_directory()
            # Bound enumeration as well as retained state; irrelevant files do
            # not allow an unbounded directory scan on the top-bar hot path.
            from itertools import islice
            paths = list(islice(self.directory.iterdir(), MAX_PACKS + 1))
            if len(paths) > MAX_PACKS:
                raise PackError('Too many files in pack directory')
            used = set(_BASE_IDS)
            for path in sorted(paths):
                if path.suffix != '.dspack':
                    continue
                try:
                    manifest, _ = _archive(_read_regular(path))
                    ids = {row['id'] for row in manifest['products']}
                    if path.name != manifest['id'] + '.dspack' or ids & used or total + len(ids) > MAX_TOTAL_PRODUCTS:
                        raise PackError('Pack inventory conflicts with installed models')
                    self._indexes[manifest['id']] = manifest
                    used.update(ids); total += len(ids)
                except PackError:
                    errors.append(path.name[:80])
            self._assert_directory()
        except (OSError, PackError):
            errors.append('directory')
            self._indexes.clear()
        self.errors = tuple(errors); self._loaded = True

    def _ensure(self):
        if not self._loaded:
            self.reload()

    def choices(self):
        self._ensure()
        return [dict(row, pack_id=pack_id) for pack_id, manifest in self._indexes.items()
                for row in deepcopy(manifest['products'])]

    def installed(self):
        self._ensure()
        result=[]
        for key,value in self._indexes.items():
            try:
                self._assert_directory()
                info=(self.directory/(key+'.dspack')).lstat()
                if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:continue
                result.append(dict(id=key,label=value['label'],version=value['version'],kind=value['kind'],
                                   products=len(value['products']),bytes=info.st_size))
            except (OSError,PackError):continue
        return result

    def get_cpu(self, model_id):
        self._ensure()
        if not isinstance(model_id, str):
            return None
        if model_id in self._selected:
            self._selected.move_to_end(model_id)
            return deepcopy(self._selected[model_id])
        match = next(((key, manifest) for key, manifest in self._indexes.items()
                      if any(row['id'] == model_id for row in manifest['products'])), None)
        if match is None:
            return None
        key, index = match
        try:
            self._assert_directory()
            manifest, models = _archive(_read_regular(self.directory / (key + '.dspack')))
            self._assert_directory()
        except PackError:
            return None
        if manifest != index:
            return None
        result = next((row for row in models if row['id'] == model_id), None)
        if result:
            self._selected[model_id] = result
            while len(self._selected) > SELECTED_CACHE_LIMIT:
                self._selected.popitem(last=False)
        return deepcopy(result)

    def install(self, source):
        raw = _read_regular(Path(source)); manifest, _ = _archive(raw)
        self._ensure()
        key = manifest['id']
        others = {row['id'] for other, index in self._indexes.items() if other != key for row in index['products']}
        ids = {row['id'] for row in manifest['products']}
        if (ids & others or len(others) + len(ids) > MAX_TOTAL_PRODUCTS
                or key not in self._indexes and len(self._indexes) >= MAX_PACKS):
            raise PackError('Pack conflicts with installed inventory limits')
        self.directory.mkdir(parents=True, exist_ok=True)
        # Refuse redirected profile-local pack directories; atomic replacement
        # never extracts archive names and never deletes a caller-supplied path.
        self._directory_identity=self._assert_directory()
        target = self.directory / (key + '.dspack')
        from itertools import islice
        files=list(islice(self.directory.iterdir(), MAX_PACKS+1))
        if len(files)+(0 if target in files else 1)>MAX_PACKS:
            raise PackError('Pack directory exceeds bounded inventory')
        if target.exists() and not stat.S_ISREG(target.lstat().st_mode):
            raise PackError('Pack destination must be a regular file')
        temporary = self.directory / (key + '-' + os.urandom(16).hex() + '.tmp')
        owned_temporary = False
        try:
            with temporary.open('xb') as stream:
                owned_temporary = True
                stream.write(raw)
            self._assert_directory()
            temporary.replace(target)
        finally:
            # Only our known, non-recursive temporary file is eligible here.
            if owned_temporary:
                try:
                    self._assert_directory()
                    if temporary.exists() and not temporary.is_symlink():temporary.unlink()
                except (OSError,PackError):pass
        self.reload()
        if key not in self._indexes:
            raise PackError('Installed pack could not be indexed')
        return key

    def remove(self, pack_id):
        _identifier(pack_id)
        self._ensure()
        if pack_id not in self._indexes:
            return False
        self._assert_directory()
        path = self.directory / (pack_id + '.dspack')
        _read_regular(path)
        self._assert_directory()
        path.unlink()
        self.reload()
        return True

    def memory_status(self):
        self._ensure()
        return dict(packs=len(self._indexes), products=sum(len(row['products']) for row in self._indexes.values()),
                    selected_records=len(self._selected), selected_record_limit=SELECTED_CACHE_LIMIT,
                    persistent_meshes=0, background_workers=0, periodic_scans=0)


_store = None


def runtime_store():
    global _store
    if _store is None:
        from profile_paths import resolve_profile_paths
        _store = PackStore(resolve_profile_paths().directory / 'hardware-packs')
    return _store
