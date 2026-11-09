"""Actual offline signatures/DPAPI with synthetic keys; no real publisher store."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import publisher_signing050 as publisher


@unittest.skipUnless(shutil.which('node'), 'Optional offline publisher requires Node.js')
class PublisherSigningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = publisher.generate_keys()

    def test_real_ed25519_signatures_require_the_trusted_key_and_exact_record(self):
        record = dict(schema='test', asset_sha256=hashlib.sha256(b'original fixture').hexdigest(), marker_id='fixture')
        receipt = publisher.sign_record(record, self.keys)
        self.assertTrue(publisher.verify_record(receipt, self.keys.public))
        changed = copy.deepcopy(receipt); changed['record']['asset_sha256'] = hashlib.sha256(b'stolen replacement').hexdigest()
        self.assertFalse(publisher.verify_record(changed, self.keys.public))
        wrong = publisher.generate_keys()
        self.assertFalse(publisher.verify_record(receipt, wrong.public))
        forged = publisher.sign_record(record, wrong)
        self.assertFalse(publisher.verify_record(forged, self.keys.public))
        for value in ({}, dict(receipt, public_key=wrong.public), dict(record=record, signature={})):
            self.assertFalse(publisher.verify_record(value, self.keys.public))

    def test_canonical_json_and_public_key_validation_fail_closed(self):
        self.assertEqual(publisher.canonical(dict(b=2, a='版权')), publisher.canonical(dict(a='版权', b=2)))
        for value in (dict(value=float('nan')), dict(value=float('inf')), dict(value=object()), {'x':'y'*(publisher.MAX_DOCUMENT+1)}):
            with self.assertRaises(publisher.PublisherError): publisher.canonical(value)
        for name, replacement in (('algorithm','RSA'),('publisher','other'),('project_url','https://example.invalid'),('key_id','0'*64)):
            public = dict(self.keys.public, **{name:replacement})
            with self.assertRaises(publisher.PublisherError): publisher.validate_public(public)
        invalid = copy.deepcopy(self.keys.public); invalid['public_key_spki_der_base64'] = 'AA=='
        with self.assertRaises(publisher.PublisherError): publisher.validate_public(invalid)

    def test_secret_values_are_not_in_repr_public_documents_or_process_arguments(self):
        private_b64 = publisher.b64(self.keys.signing_der)
        master_b64 = publisher.b64(self.keys.carrier_master)
        self.assertNotIn(private_b64, repr(self.keys)); self.assertNotIn(master_b64, repr(self.keys))
        public = publisher.canonical(self.keys.public)
        self.assertNotIn(private_b64.encode(), public); self.assertNotIn(master_b64.encode(), public)
        calls = []
        original = subprocess.run
        def capture(arguments, **kwargs):
            calls.append((arguments, kwargs.get('env', {})))
            self.assertNotIn(private_b64, repr(arguments)); self.assertNotIn(master_b64, repr(arguments))
            return original(arguments, **kwargs)
        with patch.object(subprocess,'run',side_effect=capture), patch.dict(os.environ, {'NODE_OPTIONS':'--require missing-publisher-fixture.js','NODE_PATH':'untrusted-fixture'}):
            receipt = publisher.sign_record(dict(test='pipes'), self.keys)
        self.assertTrue(publisher.verify_record(receipt, self.keys.public)); self.assertTrue(calls)
        self.assertTrue(all('NODE_OPTIONS' not in environment and 'NODE_PATH' not in environment for _,environment in calls))
        with self.assertRaises(publisher.PublisherError) as caught:
            publisher._crypto('sign', private_der='synthetic-invalid-private-data', data=publisher.b64(b'x'))
        self.assertNotIn('synthetic-invalid-private-data', str(caught.exception))

    def test_asset_carrier_keys_are_distinct_private_and_format_bound(self):
        token = bytes(range(12))
        key = self.keys.carrier_key(token, 'glb')
        self.assertEqual(len(key),32); self.assertEqual(key,self.keys.carrier_key(token,'glb'))
        self.assertNotEqual(key,self.keys.carrier_key(token,'png'))
        self.assertNotEqual(key,self.keys.carrier_key(b'changed-id!!','glb'))
        for value,kind in ((b'x','glb'),(token,'svg')):
            with self.assertRaises(publisher.PublisherError):self.keys.carrier_key(value,kind)

    def test_encrypted_portable_backup_restores_both_secrets_and_rejects_tampering(self):
        password = 'synthetic-test-password-not-an-owner-secret'
        backup = publisher.encrypted_backup(self.keys,password)
        raw = publisher.canonical(backup)
        self.assertNotIn(publisher.b64(self.keys.signing_der).encode(),raw)
        self.assertNotIn(publisher.b64(self.keys.carrier_master).encode(),raw)
        restored = publisher.open_backup(backup,password)
        self.assertEqual(restored.public,self.keys.public)
        self.assertEqual(restored.signing_der,self.keys.signing_der)
        self.assertEqual(restored.carrier_master,self.keys.carrier_master)
        with self.assertRaises(publisher.PublisherError):publisher.open_backup(backup,password+'wrong')
        changed=copy.deepcopy(backup); value=bytearray(base64.b64decode(changed['ciphertext']));value[0]^=1
        changed['ciphertext']=base64.b64encode(value).decode()
        with self.assertRaises(publisher.PublisherError):publisher.open_backup(changed,password)
        with self.assertRaises(publisher.PublisherError):publisher.encrypted_backup(self.keys,'short')

    def test_keys_cannot_be_initialized_in_the_source_repository(self):
        with self.assertRaises(publisher.PublisherError):publisher.initialize_store(publisher.PROJECT/'qa-private'/'forbidden-publisher-key')
        self.assertFalse((publisher.PROJECT/'qa-private'/'forbidden-publisher-key').exists())

    @unittest.skipUnless(os.name=='nt','DPAPI CurrentUser is a Windows publisher feature')
    def test_real_current_user_dpapi_roundtrip_tamper_and_no_overwrite(self):
        temp_base=Path(os.environ['LOCALAPPDATA'])/'Temp'
        temp_base.mkdir(exist_ok=True)
        root=Path(tempfile.mkdtemp(prefix='DesktopStats-publisher-test-',dir=temp_base))
        def cleanup():
            resolved=root.resolve()
            self.assertTrue(resolved.is_relative_to(temp_base.resolve()))
            self.assertTrue(resolved.name.startswith('DesktopStats-publisher-test-'))
            shutil.rmtree(resolved)
        self.addCleanup(cleanup)
        target=root/'new-owner-store'
        public=publisher.store_keys(self.keys,target)
        self.assertEqual(public,self.keys.public)
        raw=(target/'owner-key.dpapi').read_bytes()
        self.assertNotIn(publisher.b64(self.keys.signing_der).encode(),raw)
        self.assertNotIn(publisher.b64(self.keys.carrier_master).encode(),raw)
        loaded=publisher.load_store(target)
        self.assertEqual(loaded.carrier_master,self.keys.carrier_master)
        self.assertEqual(loaded.signing_der,self.keys.signing_der)
        with self.assertRaises(FileExistsError):publisher.store_keys(self.keys,target)
        self.assertEqual(raw,(target/'owner-key.dpapi').read_bytes())
        sealed=json.loads(raw); data=bytearray(base64.b64decode(sealed['ciphertext_base64']));data[-1]^=1
        sealed['ciphertext_base64']=base64.b64encode(data).decode();(target/'owner-key.dpapi').write_bytes(publisher.canonical(sealed))
        with self.assertRaises(publisher.PublisherError):publisher.load_store(target)


if __name__=='__main__':unittest.main()
