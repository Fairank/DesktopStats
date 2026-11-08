"""Offline publisher credentials and release signatures; never imported by Stats.

Node's existing Ed25519 implementation signs/verifies. Windows DPAPI CurrentUser
protects the local publisher bundle. No telemetry, device IDs or network calls.
"""
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parent
OWNER = 'Fairank / Desktop Stats contributors'
PROJECT_URL = 'https://github.com/Fairank/DesktopStats'
DOMAIN = b'DesktopStats.AssetRelease.v1\x00'
MAX_DOCUMENT = 2 * 1024 * 1024


class PublisherError(ValueError):
    pass


def canonical(value):
    """Deterministic signed JSON; NaN/Infinity and excessive inputs are refused."""
    try:
        data = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False).encode('utf8')
    except (ValueError, TypeError, RecursionError) as error:
        raise PublisherError('Invalid publisher document') from error
    if len(data) > MAX_DOCUMENT:
        raise PublisherError('Publisher document exceeds its size limit')
    return data


def b64(data):
    return base64.b64encode(data).decode('ascii')


def unb64(value, maximum=4096):
    if not isinstance(value, str) or len(value) > maximum * 2:
        raise PublisherError('Invalid publisher encoding')
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise PublisherError('Invalid publisher encoding') from error
    if len(data) > maximum or b64(data) != value:
        raise PublisherError('Invalid publisher encoding')
    return data


def _crypto(operation, **values):
    executable = shutil.which('node')
    if not executable:
        raise PublisherError('Offline publisher operations require Node.js; Stats does not')
    helper = PROJECT / 'tools/watermark_crypto050.mjs'
    environment = dict(os.environ)
    for name in ('NODE_OPTIONS', 'NODE_PATH', 'NODE_REPL_HISTORY'):
        environment.pop(name, None)
    # Secret fields stay on an anonymous pipe. Neither stdout nor stderr from
    # this helper is echoed into a CLI log or exception.
    result = subprocess.run([executable, str(helper)], input=canonical(dict(operation=operation, **values)),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, timeout=30,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0))
    if result.returncode or len(result.stdout) > MAX_DOCUMENT:
        raise PublisherError('Publisher cryptographic operation failed')
    try:
        return json.loads(result.stdout)
    except (ValueError, UnicodeError) as error:
        raise PublisherError('Publisher cryptographic operation failed') from error


def validate_public(public):
    if not isinstance(public, dict) or public.get('schema') != 1 or public.get('algorithm') != 'Ed25519':
        raise PublisherError('Unsupported publisher public key')
    raw = unb64(public.get('public_key_spki_der_base64'), 128)
    if len(raw) != 44 or raw[:12] != bytes.fromhex('302a300506032b6570032100'):
        raise PublisherError('Invalid Ed25519 public key')
    if public.get('key_id') != hashlib.sha256(raw).hexdigest():
        raise PublisherError('Publisher public-key fingerprint does not match')
    if public.get('publisher') != OWNER or public.get('project_url') != PROJECT_URL:
        raise PublisherError('Unexpected publisher identity')
    canonical(public)
    return raw


@dataclass(frozen=True)
class PublisherSecrets:
    public: dict
    signing_der: bytes = field(repr=False)
    carrier_master: bytes = field(repr=False)

    def carrier_key(self, token, asset_format):
        if not isinstance(token, bytes) or len(token) != 12 or asset_format not in ('glb', 'png', 'gif'):
            raise PublisherError('Invalid asset identifier or format')
        return hmac.new(self.carrier_master, b'DesktopStats.carrier.v1\0' + token + b'\0' + asset_format.encode('ascii'), hashlib.sha256).digest()


def generate_keys():
    result = _crypto('generate')
    private = unb64(result['private_der'], 256); raw_public = unb64(result['public_der'], 128)
    public = dict(schema=1, algorithm='Ed25519', publisher=OWNER, project_url=PROJECT_URL,
                  key_id=hashlib.sha256(raw_public).hexdigest(), public_key_spki_der_base64=b64(raw_public),
                  created_utc=datetime.now(timezone.utc).isoformat(), timestamp_kind='local_clock_not_trusted_timestamp')
    validate_public(public)
    return PublisherSecrets(public, private, secrets.token_bytes(32))


def _bundle(keys):
    validate_public(keys.public)
    if len(keys.carrier_master) != 32:
        raise PublisherError('Invalid publisher secret bundle')
    return canonical(dict(schema=1, public=keys.public, signing_der=b64(keys.signing_der), carrier_master=b64(keys.carrier_master)))


def _unbundle(data):
    if len(data) > 16384:
        raise PublisherError('Publisher secret bundle exceeds its size limit')
    try:
        value = json.loads(data)
        if value['schema'] != 1:
            raise PublisherError('Unsupported publisher secret bundle')
        keys = PublisherSecrets(value['public'], unb64(value['signing_der'], 256), unb64(value['carrier_master'], 32))
        _bundle(keys)
        derived = _crypto('derive_public', private_der=b64(keys.signing_der))['public_der']
        if not hmac.compare_digest(derived, keys.public['public_key_spki_der_base64']):
            raise PublisherError('Publisher key pair does not match')
        return keys
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise PublisherError('Invalid publisher secret bundle') from error


def _dpapi(data, decrypt=False):
    if os.name != 'nt':
        raise PublisherError('Local publisher keys use Windows DPAPI CurrentUser')
    if not isinstance(data, bytes) or len(data) > MAX_DOCUMENT:
        raise PublisherError('Invalid protected-key data')
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    def blob(raw):
        keep = ctypes.create_string_buffer(raw)
        return Blob(len(raw), ctypes.cast(keep, ctypes.POINTER(ctypes.c_ubyte))), keep
    source, source_keep = blob(data)
    entropy, entropy_keep = blob(b'DesktopStats.publisher.DPAPI.CurrentUser.v1')
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]; kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        function = crypt.CryptUnprotectData
        function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        args = (ctypes.byref(source), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(output))
    else:
        function = crypt.CryptProtectData
        function.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob),
                             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        args = (ctypes.byref(source), 'DesktopStats offline publisher key', ctypes.byref(entropy), None, None, 1, ctypes.byref(output))
    function.restype = wintypes.BOOL
    if not function(*args):
        raise PublisherError('Current Windows user could not protect or open the publisher key')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(ctypes.cast(output.data, ctypes.c_void_p))


def default_key_directory():
    base = os.environ.get('LOCALAPPDATA')
    if not base:
        raise PublisherError('The Windows local application-data folder is unavailable')
    return Path(base) / 'DesktopStatsPublisher' / 'watermark-owner-v1'


def _store_path(directory):
    path = Path(directory if directory is not None else default_key_directory()).absolute()
    resolved = path.resolve()
    profile = Path(os.environ.get('USERPROFILE', str(Path.home()))).resolve()
    if path != resolved or resolved == profile or not resolved.is_relative_to(profile):
        raise PublisherError('Publisher keys must use a real folder inside the current user profile')
    if resolved == PROJECT or resolved.is_relative_to(PROJECT):
        raise PublisherError('Publisher secrets must never be placed in the project repository')
    for parent in (path, *path.parents):
        if parent.exists():
            information = parent.lstat()
            if parent.is_symlink() or getattr(information, 'st_file_attributes', 0) & 0x400:
                raise PublisherError('Publisher secret paths cannot use reparse points')
    return resolved


def _restrict_new_directory(path):
    if os.name != 'nt':
        raise PublisherError('Publisher key storage requires Windows')
    # Read the current token's SID without encoding or logging its display name.
    import ctypes
    from ctypes import wintypes
    class TokenUser(ctypes.Structure):
        _fields_ = [('sid', ctypes.c_void_p), ('attributes', wintypes.DWORD)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]; kernel.LocalFree.restype = ctypes.c_void_p
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.GetTokenInformation.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    token = wintypes.HANDLE(); needed = wintypes.DWORD(); text = wintypes.LPWSTR()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise PublisherError('Could not restrict the publisher-key folder')
    try:
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        if not 0 < needed.value < 65536:
            raise PublisherError('Could not restrict the publisher-key folder')
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(token, 1, buffer, needed, ctypes.byref(needed)):
            raise PublisherError('Could not restrict the publisher-key folder')
        user = ctypes.cast(buffer, ctypes.POINTER(TokenUser)).contents
        if not advapi.ConvertSidToStringSidW(user.sid, ctypes.byref(text)):
            raise PublisherError('Could not restrict the publisher-key folder')
        sid = text.value
    finally:
        if text: kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))
        kernel.CloseHandle(token)
    result = subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
        '*'+sid+':(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    if result.returncode:
        raise PublisherError('Could not restrict the publisher-key folder')


def _write_new(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def store_keys(keys, directory=None):
    path = _store_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(exist_ok=False)
    try:
        _restrict_new_directory(path)
        _unbundle(_bundle(keys))
        protected = dict(schema=1, protection='Windows-DPAPI-CurrentUser', key_id=keys.public['key_id'],
                         ciphertext_base64=b64(_dpapi(_bundle(keys))))
        _write_new(path / 'owner-key.dpapi', canonical(protected))
        _write_new(path / 'publisher-public.json', canonical(keys.public) + b'\n')
        return keys.public
    except Exception:
        # Only remove this newly created directory when it is still empty.
        try: path.rmdir()
        except OSError: pass
        raise


def initialize_store(directory=None):
    return store_keys(generate_keys(), directory)


def load_store(directory=None):
    path = _store_path(directory)
    private = path / 'owner-key.dpapi'
    _store_path(private)
    if private.stat().st_size > 32768:
        raise PublisherError('Protected publisher key exceeds its size limit')
    try:
        record = json.loads(private.read_bytes())
        if record['schema'] != 1 or record['protection'] != 'Windows-DPAPI-CurrentUser':
            raise PublisherError('Unsupported protected publisher key')
        keys = _unbundle(_dpapi(unb64(record['ciphertext_base64'], 16384), decrypt=True))
        if not hmac.compare_digest(record['key_id'], keys.public['key_id']):
            raise PublisherError('Protected publisher key fingerprint does not match')
        public_file = path / 'publisher-public.json'
        _store_path(public_file)
        if public_file.exists() and canonical(json.loads(public_file.read_bytes())) != canonical(keys.public):
            raise PublisherError('Local public-key copy does not match the protected publisher')
        return keys
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise PublisherError('The protected publisher key could not be opened') from error


def sign_record(record, keys):
    data = DOMAIN + canonical(record)
    signature = _crypto('sign', private_der=b64(keys.signing_der), data=b64(data))['signature']
    receipt = dict(record=record, signature=dict(algorithm='Ed25519', key_id=keys.public['key_id'], signature_base64=signature))
    if not verify_record(receipt, keys.public):
        raise PublisherError('Publisher signature self-check failed')
    return receipt


def verify_record(receipt, trusted_public):
    raw_public = validate_public(trusted_public)
    try:
        if not isinstance(receipt, dict) or set(receipt) != {'record', 'signature'}:
            return False
        signature = receipt['signature']
        if signature['algorithm'] != 'Ed25519' or signature['key_id'] != trusted_public['key_id']:
            return False
        raw = unb64(signature['signature_base64'], 64)
        if len(raw) != 64:
            return False
        return _crypto('verify', public_der=b64(raw_public), data=b64(DOMAIN + canonical(receipt['record'])), signature=b64(raw))['valid'] is True
    except (KeyError, TypeError, ValueError, PublisherError):
        return False


def encrypted_backup(keys, password):
    return _crypto('seal', password=password, data=b64(_bundle(keys)))


def open_backup(backup, password):
    result = _crypto('open', backup=backup, password=password)
    return _unbundle(unb64(result['data'], 16384))
