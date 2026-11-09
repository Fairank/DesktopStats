"""Offline original-asset watermark publisher; never runs inside DesktopStats.

Use a trusted public-key file for verification. Hidden mark extraction requires
the owner's separate local carrier key; a public signature is not an extractor.
"""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from publisher_signing050 import (OWNER, PROJECT_URL, PublisherError, canonical,
    initialize_store, load_store, validate_public, sign_record, verify_record,
    encrypted_backup, open_backup, store_keys)

MAX_ASSET = 64 * 1024 * 1024
MAX_RECEIPT = 2 * 1024 * 1024
SCHEMA = 'DesktopStats.asset-watermark.1'


def _read(path, maximum):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > maximum:
        raise PublisherError('Input is missing or exceeds its size limit')
    data = path.read_bytes()
    if len(data) > maximum:
        raise PublisherError('Input exceeds its size limit')
    return data


def _json(path, maximum=MAX_RECEIPT):
    try:
        return json.loads(_read(path, maximum))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise PublisherError('Invalid publisher JSON document') from error


def _write_new(path, data):
    path = Path(path).absolute()
    if path != path.resolve():
        raise PublisherError('Output must use a real path, without symbolic links')
    for parent in path.parents:
        if parent.exists() and (parent.is_symlink() or getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400):
            raise PublisherError('Output cannot traverse a reparse point')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def _format(data):
    if data.startswith(b'glTF'):
        return 'glb'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if data.startswith((b'GIF87a', b'GIF89a')):
        return 'gif'
    raise PublisherError('Only the tested GLB, PNG and GIF formats are supported')


def _codec(asset_format):
    if asset_format == 'glb':
        from geometry_watermark050 import mark_glb, extract_glb
        return mark_glb, extract_glb
    from image_watermark050 import mark_image, extract_image
    return mark_image, extract_image


def _context(report):
    context = report.get('context', report.get('public_context'))
    if not isinstance(context, dict):
        raise PublisherError('Codec omitted its public extraction context')
    return context


def _decoded(asset_format, result):
    if asset_format != 'glb':
        return dict(result, complete_asset_marker=result.get('matched') is True,
                    origin_match=result.get('matched') is True,
                    marker_scope='image' if result.get('matched') is True else 'no-match')
    whole = result.get('global_channel', {})
    complete = (whole.get('exact_match') is True and result.get('all_context_groups_present') is True
                and result.get('all_context_instances_present') is True)
    origin = result.get('detected') is True
    return dict(result, matched=complete, bit_errors=whole.get('bit_errors'),
        complete_asset_marker=complete, origin_match=origin,
        marker_scope='all-reference-groups' if complete else 'reference-component' if origin else 'no-match')


def _public_report(value, keys, carrier_key):
    """Reject accidental secret or carrier-position output before signing it."""
    forbidden = {'key', 'private_key', 'signing_der', 'carrier_key', 'carrier_master',
                 'seed', 'seed_hex', 'secret', 'selected_carriers', 'carrier_order', 'carrier_positions'}
    def visit(item, depth=0):
        if depth > 24:
            raise PublisherError('Watermark report is too deeply nested')
        if isinstance(item, dict):
            for name, child in item.items():
                if not isinstance(name, str) or name.casefold() in forbidden:
                    raise PublisherError('A codec tried to publish a private watermark field')
                visit(child, depth + 1)
        elif isinstance(item, (tuple, list)):
            for child in item: visit(child, depth + 1)
        elif not isinstance(item, (str, int, float, bool, type(None))):
            raise PublisherError('Watermark report contains an unsupported value')
    visit(value)
    raw = canonical(value)
    import base64
    for secret in (keys.signing_der, keys.carrier_master, carrier_key):
        if secret.hex().encode('ascii') in raw or base64.b64encode(secret) in raw:
            raise PublisherError('A codec tried to publish watermark secret material')
    return value


def _record(receipt, trusted_public):
    if not verify_record(receipt, trusted_public):
        raise PublisherError('The release signature does not match the trusted publisher key')
    record = receipt['record']
    if not isinstance(record, dict) or record.get('schema') != SCHEMA:
        raise PublisherError('Unsupported signed watermark record')
    if record.get('publisher') != OWNER or record.get('project_url') != PROJECT_URL:
        raise PublisherError('Unexpected signed publisher identity')
    if not isinstance(record.get('marker_id'), str) or not re.fullmatch('[0-9a-f]{24}', record['marker_id']):
        raise PublisherError('Invalid signed marker identifier')
    if record.get('format') not in ('glb', 'png', 'gif') or not isinstance(record.get('context'), dict):
        raise PublisherError('Invalid signed codec context')
    for name in ('original_sha256', 'marked_sha256', 'source_commit'):
        size = 40 if name == 'source_commit' else 64
        if not isinstance(record.get(name), str) or not re.fullmatch('[0-9a-f]{'+str(size)+'}', record[name]):
            raise PublisherError('Invalid signed source or asset digest')
    return record


def mark_asset(source, destination, keys, source_commit, source_reference=''):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    receipt_path = destination.with_name(destination.name + '.watermark.json')
    if source.resolve() == destination.resolve() or destination.exists() or receipt_path.exists():
        raise PublisherError('Refusing to replace an original asset or existing marked release')
    if not re.fullmatch('[0-9a-f]{40}', source_commit):
        raise PublisherError('A pinned source commit is required')
    if not isinstance(source_reference, str) or len(source_reference) > 2048:
        raise PublisherError('Invalid public source reference')
    if source_reference and not source_reference.startswith('https://github.com/Fairank/DesktopStats/') and not source_reference.startswith('https://raw.githubusercontent.com/Fairank/DesktopStats/'):
        raise PublisherError('Source reference must point to this public repository')
    data = _read(source, MAX_ASSET); asset_format = _format(data)
    if destination.suffix.casefold() != '.' + asset_format:
        raise PublisherError('Marked output extension does not match its actual format')
    token = secrets.token_bytes(12); carrier_key = keys.carrier_key(token, asset_format)
    embed, extract = _codec(asset_format)
    marked, report = embed(data, token, carrier_key)
    report = _public_report(report, keys, carrier_key)
    if not isinstance(marked, bytes) or len(marked) > MAX_ASSET or _format(marked) != asset_format:
        raise PublisherError('Codec produced an invalid or oversized asset')
    context = _context(report)
    check = _decoded(asset_format, extract(marked, carrier_key, token, context))
    check = _public_report(check, keys, carrier_key)
    if check.get('matched') is not True or check.get('bit_errors') != 0:
        raise PublisherError('Hidden watermark could not be extracted before publication')
    if _read(source, MAX_ASSET) != data:
        raise PublisherError('Original asset changed during publication')
    tool_sources = {}
    for name in ('publisher_signing050.py', 'geometry_watermark050.py', 'image_watermark050.py',
                 'tools/watermark_assets050.py', 'tools/watermark_crypto050.mjs'):
        path = ROOT / name
        tool_sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    record = dict(schema=SCHEMA, publisher=OWNER, project_url=PROJECT_URL,
        marker_id=token.hex(), format=asset_format, asset_name=destination.name,
        original_sha256=hashlib.sha256(data).hexdigest(), marked_sha256=hashlib.sha256(marked).hexdigest(),
        original_bytes=len(data), marked_bytes=len(marked), source_commit=source_commit,
        source_reference=source_reference, codec=report.get('scheme', report.get('profile', 'see-context')), context=context,
        embedding_report=report, extraction_before_publication=check, tool_source_sha256=tool_sources,
        created_utc=datetime.now(timezone.utc).isoformat(), timestamp_kind='local_clock_not_trusted_timestamp',
        license='PolyForm-Noncommercial-1.0.0; original project material only; existing third-party rights remain',
        purpose='Publisher-origin evidence assistance, not a copyright or court determination',
        not_user_specific=True, no_tracking=True, runtime_embedding=False)
    record = _public_report(record, keys, carrier_key)
    receipt = sign_record(record, keys)
    if _record(receipt, keys.public) != record:
        raise PublisherError('Signed release record did not verify')
    _write_new(destination, marked)
    _write_new(receipt_path, canonical(receipt) + b'\n')
    return dict(asset=destination.name, receipt=receipt_path.name, format=asset_format,
        marker_id=token.hex(), original_sha256=record['original_sha256'], marked_sha256=record['marked_sha256'],
        signature_verified=True, marker_extracted=True, original_unchanged=True)


def verify_asset(candidate, receipt, trusted_public):
    record = _record(receipt, trusted_public)
    data = _read(candidate, MAX_ASSET)
    return dict(release_signature_valid=True, trusted_key_id=trusted_public['key_id'],
        candidate_sha256=hashlib.sha256(data).hexdigest(),
        candidate_matches_signed_bytes=hashlib.sha256(data).hexdigest() == record['marked_sha256'],
        marker_extraction_performed=False, legal_conclusion=False)


def detect_asset(candidate, receipt, trusted_public, keys):
    record = _record(receipt, trusted_public)
    if keys.public['key_id'] != trusted_public['key_id']:
        raise PublisherError('Extraction key does not belong to the trusted publisher')
    data = _read(candidate, MAX_ASSET)
    if _format(data) != record['format']:
        raise PublisherError('Candidate format differs from the signed watermark record')
    token = bytes.fromhex(record['marker_id']); carrier_key = keys.carrier_key(token, record['format'])
    _, extract = _codec(record['format'])
    check = _public_report(_decoded(record['format'], extract(data, carrier_key, token, record['context'])), keys, carrier_key)
    digest = hashlib.sha256(data).hexdigest()
    result = dict(release_signature_valid=True, trusted_key_id=trusted_public['key_id'],
        candidate_sha256=digest, candidate_matches_signed_bytes=digest == record['marked_sha256'])
    result.update(marker_extraction_performed=True, embedded_origin_match=check.get('origin_match') is True,
        marker_scope=check['marker_scope'],
        extraction=check, marker_id=record['marker_id'], legal_conclusion=False,
        statement='A matching hidden release identifier is not a signature on altered bytes or a legal conclusion.')
    return result


def _password(confirm=False):
    first = getpass.getpass('Publisher backup password (at least16 characters): ')
    if len(first) < 16:
        raise PublisherError('Use a backup password of at least16 characters')
    if confirm and first != getpass.getpass('Repeat backup password: '):
        raise PublisherError('Backup passwords do not match')
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('key-init', 'key-public', 'key-backup', 'key-restore', 'mark', 'verify', 'detect'):
        command = commands.add_parser(name)
        if name != 'verify': command.add_argument('--key-dir', type=Path)
        if name in ('key-init', 'key-public'): command.add_argument('--public-output', type=Path)
        if name in ('key-backup', 'key-restore'): command.add_argument('--backup', type=Path, required=True)
        if name == 'mark':
            command.add_argument('--input', type=Path, required=True); command.add_argument('--output', type=Path, required=True)
            command.add_argument('--source-commit', required=True); command.add_argument('--source-reference', default='')
        if name in ('verify', 'detect'):
            command.add_argument('--input', type=Path, required=True); command.add_argument('--receipt', type=Path, required=True)
            command.add_argument('--public-key', type=Path, required=True)
        if name == 'detect': command.add_argument('--report-output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'key-init':
            public = initialize_store(args.key_dir)
            if args.public_output: _write_new(args.public_output, canonical(public) + b'\n')
            result = dict(initialized=True, key_id=public['key_id'], private_key_printed=False)
        elif args.command == 'key-public':
            public = load_store(args.key_dir).public
            if args.public_output: _write_new(args.public_output, canonical(public) + b'\n')
            result = public
        elif args.command == 'key-backup':
            backup = encrypted_backup(load_store(args.key_dir), _password(confirm=True))
            if args.backup.absolute().resolve().is_relative_to(ROOT):
                raise PublisherError('Encrypted publisher backups must also stay outside the repository')
            _write_new(args.backup, canonical(backup) + b'\n')
            result = dict(encrypted_backup_written=True, private_key_printed=False)
        elif args.command == 'key-restore':
            public = store_keys(open_backup(_json(args.backup, 32768), _password()), args.key_dir)
            result = dict(restored=True, key_id=public['key_id'], private_key_printed=False)
        elif args.command == 'mark':
            result = mark_asset(args.input, args.output, load_store(args.key_dir), args.source_commit, args.source_reference)
        else:
            public = _json(args.public_key, 32768); validate_public(public); receipt = _json(args.receipt)
            if args.command == 'verify':
                result = verify_asset(args.input, receipt, public)
            else:
                keys = load_store(args.key_dir)
                result = detect_asset(args.input, receipt, public, keys)
                if args.report_output: _write_new(args.report_output, canonical(sign_record(result, keys)) + b'\n')
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if args.command == 'verify': return 0 if result['candidate_matches_signed_bytes'] else 1
        if args.command == 'detect': return 0 if result['embedded_origin_match'] else 1
        return 0
    except (PublisherError, OSError, ValueError, TypeError, RecursionError, KeyError):
        # Never echo an input document, a password or helper-provider output.
        print('Offline watermark operation failed; verify the input, trusted public key and supported codec.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
