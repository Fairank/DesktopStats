"""End-to-end release evidence: signature, byte identity and mark are distinct."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from contextlib import redirect_stdout,redirect_stderr
from unittest.mock import patch
import zlib

import publisher_signing050 as signer
from tools import watermark_assets050 as publisher


def chunk(name, data):
    return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)


def png():
    width=48;height=40
    rows=bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):rows.extend((x%200,y%200,(x*7+y*11)%256,255))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+
            chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))


@unittest.skipUnless(shutil.which('node'),'Offline publisher requires optional Node.js')
class WatermarkPublisherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.keys=signer.generate_keys()

    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'qa-private'/'publisher-integration050'
        root.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(temp.cleanup);self.base=Path(temp.name)
        self.source=self.base/'original.png';self.source.write_bytes(png())
        self.output=self.base/'protected.png'

    def mark(self):
        result=publisher.mark_asset(self.source,self.output,self.keys,'1'*40)
        receipt=json.loads(self.output.with_name(self.output.name+'.watermark.json').read_bytes())
        return result,receipt

    def test_actual_mark_verify_and_metadata_change_keep_three_results_separate(self):
        original=self.source.read_bytes();result,receipt=self.mark()
        self.assertTrue(result['signature_verified']);self.assertEqual(self.source.read_bytes(),original)
        exact=publisher.verify_asset(self.output,receipt,self.keys.public)
        self.assertTrue(exact['release_signature_valid']);self.assertTrue(exact['candidate_matches_signed_bytes'])
        check=publisher.detect_asset(self.output,receipt,self.keys.public,self.keys)
        self.assertTrue(check['embedded_origin_match']);self.assertEqual(check['extraction']['bit_errors'],0)
        raw=self.output.read_bytes();changed=raw[:33]+chunk(b'tEXt',b'Editor\0synthetic repack')+raw[33:]
        edited=self.base/'renamed-metadata.png';edited.write_bytes(changed)
        check=publisher.detect_asset(edited,receipt,self.keys.public,self.keys)
        self.assertTrue(check['release_signature_valid']);self.assertFalse(check['candidate_matches_signed_bytes'])
        self.assertTrue(check['embedded_origin_match']);self.assertFalse(check['legal_conclusion'])
        self.assertFalse(publisher.verify_asset(edited,receipt,self.keys.public)['candidate_matches_signed_bytes'])
        public=self.base/'trusted-public.json';public.write_bytes(signer.canonical(self.keys.public))
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            status=publisher.main(['verify','--input',str(edited),'--receipt',str(self.output)+'.watermark.json','--public-key',str(public)])
        self.assertEqual(status,1)

    def test_wrong_trusted_key_forged_record_and_wrong_extractor_never_match(self):
        _,receipt=self.mark();other=signer.generate_keys()
        for wrong in (other.public,):
            with self.assertRaises(signer.PublisherError):publisher.verify_asset(self.output,receipt,wrong)
        changed=copy.deepcopy(receipt);changed['record']['marked_sha256']='0'*64
        with self.assertRaises(signer.PublisherError):publisher.verify_asset(self.output,changed,self.keys.public)
        with self.assertRaises(signer.PublisherError):publisher.detect_asset(self.output,receipt,self.keys.public,other)

    def test_an_unmarked_asset_is_not_a_detected_copy(self):
        _,receipt=self.mark()
        check=publisher.detect_asset(self.source,receipt,self.keys.public,self.keys)
        self.assertFalse(check['candidate_matches_signed_bytes']);self.assertFalse(check['embedded_origin_match'])
        self.assertFalse(check['legal_conclusion'])

    def test_original_and_previously_marked_releases_are_never_overwritten(self):
        original=self.source.read_bytes()
        with self.assertRaises(signer.PublisherError):publisher.mark_asset(self.source,self.source,self.keys,'1'*40)
        self.mark();before=self.output.read_bytes()
        with self.assertRaises(signer.PublisherError):self.mark()
        self.assertEqual(self.source.read_bytes(),original);self.assertEqual(self.output.read_bytes(),before)

    def test_codec_secret_leak_is_refused_before_writing_any_release(self):
        token=bytes(range(12));carrier=self.keys.carrier_key(token,'png')
        def leak(*args):return b'\x89PNG\r\n\x1a\nfixture',dict(context={},carrier_key=carrier.hex())
        with patch.object(publisher,'_codec',return_value=(leak,lambda *args:dict(matched=True,bit_errors=0))):
            with self.assertRaises(signer.PublisherError):self.mark()
        self.assertFalse(self.output.exists());self.assertEqual(self.source.read_bytes(),png())

    def test_detect_hashes_the_same_snapshot_that_was_extracted(self):
        _,receipt=self.mark();reads=[];original=publisher._read
        def read(path,maximum):
            if Path(path)==self.output:reads.append(path)
            return original(path,maximum)
        with patch.object(publisher,'_read',side_effect=read):
            result=publisher.detect_asset(self.output,receipt,self.keys.public,self.keys)
        self.assertEqual(len(reads),1);self.assertTrue(result['embedded_origin_match'])
        self.assertEqual(result['candidate_sha256'],hashlib.sha256(self.output.read_bytes()).hexdigest())

    def test_unsupported_format_and_unpinned_source_are_not_silently_published(self):
        self.source.write_bytes(b'not an image')
        with self.assertRaises(signer.PublisherError):self.mark()
        self.assertFalse(self.output.exists())
        self.source.write_bytes(png())
        with self.assertRaises(signer.PublisherError):publisher.mark_asset(self.source,self.output,self.keys,'main')
        self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
