"""Real RGB carriers, independent software decode, and bounded offline input.

All keys/tokens below are public synthetic fixtures, never publisher secrets.
Optional DS_IMAGE_WATERMARK_QA_DIR preserves new marked QA copies/receipts only.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import time
import tracemalloc
import unittest
import zlib

import image_watermark050 as wm


TOKEN = bytes(range(12))
KEY = bytes(range(32))
ROOT = Path(__file__).resolve().parents[1]
MASK_LOW_BIT = bytes(value & 254 for value in range(256))


def chunk(kind, payload):
    return (struct.pack('>I', len(payload)) + kind + payload
            + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff))


def paeth(a, b, c):
    p = a + b - c
    distances = (abs(p - a), abs(p - b), abs(p - c))
    return (a, b, c)[distances.index(min(distances))]


def png(width=32, height=24, channels=4, modes=(0, 1, 2, 3, 4), partial=False, metadata=True):
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            pixels.extend(((x * 17 + y * 3) % 256, (x * 5 + y * 19) % 256,
                           (x * 11 + y * 7) % 256))
            if channels == 4:
                pixels.append((0, 64, 254, 255)[x % 4] if partial else 255)
    stride = width * channels
    filtered = bytearray()
    previous = bytes(stride)
    for y in range(height):
        row = pixels[y * stride:(y + 1) * stride]
        mode = modes[y % len(modes)]
        filtered.append(mode)
        for i, value in enumerate(row):
            a = row[i - channels] if i >= channels else 0
            b = previous[i]
            c = previous[i - channels] if i >= channels else 0
            predictor = (0, a, b, (a + b) // 2, paeth(a, b, c))[mode]
            filtered.append((value - predictor) & 255)
        previous = row
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2 if channels == 3 else 6, 0, 0, 0)
    encoded = zlib.compress(filtered)
    data = wm._PNG_MAGIC + chunk(b'IHDR', ihdr)
    if metadata:
        data += chunk(b'tEXt', b'Fixture\0No token or key is stored here')
    data += chunk(b'IDAT', encoded[:len(encoded) // 2])
    data += chunk(b'IDAT', encoded[len(encoded) // 2:]) + chunk(b'IEND', b'')
    return data, bytes(pixels)


def png_without_metadata(data):
    result = bytearray(data[:8])
    at = 8
    while at < len(data):
        size = struct.unpack_from('>I', data, at)[0] + 12
        if not data[at + 4] & 32:
            result.extend(data[at:at + size])
        at += size
    return bytes(result)


def blocks(raw):
    return b''.join(bytes((len(raw[at:at + 255]),)) + raw[at:at + 255]
                    for at in range(0, len(raw), 255)) + b'\0'


def gif_indices(indices):
    # A clear before every pixel keeps this independent fixture encoder at9bits.
    codes = [value for index in indices for value in (256, index)] + [257]
    bits = 0
    count = 0
    result = bytearray()
    for code in codes:
        bits |= code << count
        count += 9
        while count >= 8:
            result.append(bits & 255)
            bits >>= 8
            count -= 8
    if count:
        result.append(bits)
    return b'\x08' + blocks(result)


def gif(palette=None, local=True, transparent=True, order=None):
    colors = palette or [(2 * (i % 128), 2 * (i // 128), 42) for i in range(256)]
    if order is None:
        order = list(range(256))
    inverse = {old: new for new, old in enumerate(order)}
    table = bytes(channel for index in order for channel in colors[index])
    data = bytearray(b'GIF89a' + struct.pack('<HHBBB', 16, 16, 0xf7, 0, 0) + table)
    data.extend(b'!\xff\x0bNETSCAPE2.0\x03\x01\x02\x00\x00')
    data.extend(b'!\xfe' + blocks(b'Removable comment without watermark payload'))
    for frame in range(2 if local else 1):
        trans_index = inverse[0]
        data.extend(b'!\xf9\x04' + bytes((9 if transparent else 8,))
                    + struct.pack('<H', 7 + frame * 5) + bytes((trans_index, 0)))
        data.extend(b',' + struct.pack('<HHHHB', 0, 0, 16, 16, 0x87 if frame else 0))
        if frame:
            data.extend(table)
        data.extend(gif_indices([inverse[i] for i in range(256)]))
    return bytes(data) + b';'


def compare_decoded(before, after):
    """Independent Qt image codec only: no GUI application, window, or GL."""
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    from PySide6.QtGui import QImage, QImageReader
    readers = []
    holders = []
    for data in (before, after):
        buf = QBuffer()
        buf.setData(QByteArray(data))
        assert buf.open(QIODevice.ReadOnly)
        holders.append(buf)
        readers.append(QImageReader(buf))
    counts = [reader.imageCount() for reader in readers]
    assert counts[0] == counts[1] and 0 < counts[0] <= wm.MAX_GIF_FRAMES
    loops = [reader.loopCount() for reader in readers]
    assert loops[0] == loops[1]
    delays = []
    changed_frames = 0
    maximum = 0
    for _ in range(counts[0]):
        images = [reader.read().convertToFormat(QImage.Format_RGBA8888) for reader in readers]
        assert all(not image.isNull() for image in images)
        assert images[0].size() == images[1].size()
        raw = [bytes(image.constBits()) for image in images]
        assert raw[0][3::4] == raw[1][3::4], 'Decoded alpha changed'
        assert raw[0].translate(MASK_LOW_BIT) == raw[1].translate(MASK_LOW_BIT), 'RGB delta exceeds1'
        changed_frames += raw[0] != raw[1]
        maximum = max(maximum, int(raw[0] != raw[1]))
        delay = [reader.nextImageDelay() for reader in readers]
        assert delay[0] == delay[1]
        delays.append(delay[0])
    return dict(frames=counts[0], loop_count=loops[0], delays_ms=delays,
                alpha_equal=True, max_decoded_channel_delta=maximum,
                changed_frames=changed_frames, decoder='Qt QImageReader software; no window/GL')


class ImageWatermark050Tests(unittest.TestCase):
    def roundtrip(self, data):
        original = hashlib.sha256(data).digest()
        marked, report = wm.mark_image(data, TOKEN, KEY)
        self.assertEqual(hashlib.sha256(data).digest(), original)
        extracted = wm.extract_image(marked, KEY, TOKEN, report['context'])
        self.assertTrue(extracted['matched'])
        self.assertEqual(extracted['bit_errors'], 0)
        self.assertEqual(extracted['raw_bit_errors'], 0)
        self.assertNotEqual(data, marked)
        self.assertNotIn(KEY.hex(), json.dumps(report))
        return marked, report

    def test_png_all_five_filters_and_rgb_rgba(self):
        for channels in (3, 4):
            with self.subTest(channels=channels):
                data, original = png(channels=channels)
                self.assertEqual(bytes(wm._Png(data).pixels), original)
                marked, report = self.roundtrip(data)
                decoded = bytes(wm._Png(marked).pixels)
                for at, (a, b) in enumerate(zip(original, decoded)):
                    self.assertLessEqual(abs(a - b), 1)
                    if at % channels != 2:
                        self.assertEqual(a, b)
                self.assertEqual(compare_decoded(data, marked)['max_decoded_channel_delta'], 1)
                stripped = png_without_metadata(marked)
                self.assertTrue(wm.extract_image(stripped, KEY, TOKEN, report['context'])['matched'])

    def test_partial_alpha_and_transparent_rgb_unchanged(self):
        data, original = png(width=64, height=32, partial=True)
        marked, report = self.roundtrip(data)
        pixels = wm._Png(marked).pixels
        self.assertEqual(report['carrier_count'], 64 * 32 // 4)
        for at in range(0, len(original), 4):
            if original[at + 3] != 255:
                self.assertEqual(original[at:at + 4], pixels[at:at + 4])
            self.assertEqual(original[at + 3], pixels[at + 3])
        compare_decoded(data, marked)

    def test_wrong_key_wrong_token_and_unmarked_are_negative(self):
        for data in (png()[0], gif()):
            marked, report = self.roundtrip(data)
            for candidate, key, token in ((data, KEY, TOKEN),
                                          (marked, bytes(reversed(KEY)), TOKEN),
                                          (marked, KEY, b'wrong-token!')):
                result = wm.extract_image(candidate, key, token, report['context'])
                self.assertFalse(result['matched'])
                self.assertGreater(result['bit_errors'], 0)

    def test_gif_global_local_transparency_animation_and_nonpalette_bytes(self):
        data = gif()
        marked, report = self.roundtrip(data)
        parsed = wm._Gif(data)
        self.assertEqual(parsed.palette_count, 2)
        self.assertEqual(report['repetition'], 7)
        self.assertLessEqual(report['changed_carriers'], report['used_carriers'])
        self.assertGreater(report['changed_rgb_samples'], report['changed_carriers'])
        allowed = {at for start, end in parsed.palette_ranges for at in range(start, end)}
        for at, (a, b) in enumerate(zip(data, marked)):
            if at not in allowed:
                self.assertEqual(a, b)
            else:
                self.assertLessEqual(abs(a - b), 1)
        # The transparent group is untouched in every copy of the table.
        for start, _ in parsed.palette_ranges:
            self.assertEqual(data[start:start + 3], marked[start:start + 3])
        decoded = compare_decoded(data, marked)
        self.assertEqual(decoded['frames'], 2)
        self.assertEqual(decoded['loop_count'], 2)
        comment = b'!\xfe' + blocks(b'Removable comment without watermark payload')
        self.assertTrue(wm.extract_image(marked.replace(comment, b''), KEY, TOKEN, report['context'])['matched'])

    def test_gif_palette_order_has_no_identity_dependency(self):
        data = gif(local=False)
        marked, report = self.roundtrip(data)
        parsed = wm._Gif(marked)
        # Recreate the same marked RGB palette/indices in a different order.
        start, end = parsed.palette_ranges[0]
        colors = [tuple(marked[at:at + 3]) for at in range(start, end, 3)]
        reordered = gif(palette=colors, local=False, order=list(reversed(range(256))))
        self.assertTrue(wm.extract_image(reordered, KEY, TOKEN, report['context'])['matched'])
        compare_decoded(marked, reordered)

    def test_repetition_majority_and_capacity_failure(self):
        for count, expected in ((288, 3), (480, 5), (672, 7)):
            data, _ = png(width=count, height=1)
            marked, report = self.roundtrip(data)
            self.assertEqual(report['repetition'], expected)
            image = wm._Png(marked)
            ranks, _ = wm._plan(KEY, report['context'])
            positions = image.positions(ranks)
            for rank in ranks[:96]:
                image.pixels[positions[rank]] ^= 1
            # Encode these altered real pixels without assigning new payload.
            corrupted, _ = image.mark([], [])
            result = wm.extract_image(corrupted, KEY, TOKEN, report['context'])
            self.assertTrue(result['matched'])
            self.assertEqual(result['raw_bit_errors'], 96)
        for data in (png(width=16, height=16)[0],
                     png(width=32, height=16, partial=True)[0],
                     gif(palette=[(0, 0, 0), (254, 254, 254)] * 128)):
            with self.assertRaises(wm.WatermarkError):
                wm.mark_image(data, TOKEN, KEY)

    def test_high_seven_bit_conflicts_skip_and_cannot_collapse_after_mark(self):
        colors = [(2 * (i % 128), 2 * (i // 128), 42) for i in range(256)]
        colors[1] = (1, 0, 42)  # Same canonical key as0, different actual RGB.
        data = gif(palette=colors, local=False, transparent=False)
        marked, report = self.roundtrip(data)
        self.assertEqual(wm._Gif(data).skipped_groups, 1)
        self.assertEqual(data[13:19], marked[13:19])
        self.assertEqual(wm._Gif(data).context(), wm._Gif(marked).context())
        self.assertGreater(report['carrier_count'], 672)

    def test_malformed_dimensions_crc_and_decompression_bomb_fail_closed(self):
        good = png()[0]
        bomb = (wm._PNG_MAGIC + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(bytes(2 * 1024 * 1024))) + chunk(b'IEND', b''))
        huge = (wm._PNG_MAGIC + chunk(b'IHDR', struct.pack('>IIBBBBB', 8193, 1, 8, 6, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(b'')) + chunk(b'IEND', b''))
        gif_huge = bytearray(gif())
        struct.pack_into('<HH', gif_huge, 6, 65535, 65535)
        invalid_crc = good[:31] + bytes((good[31] ^ 1,)) + good[32:]
        single = gif(local=False)
        control_at = single.index(b'!\xf9\x04')
        too_many_frames = single[:control_at] + single[control_at:-1] * (wm.MAX_GIF_FRAMES + 1) + b';'
        for data in (bomb, huge, bytes(gif_huge), invalid_crc, good[:-1], gif()[:-1],
                     good + b'extra', too_many_frames, b'GIF89a', b'not an image'):
            with self.subTest(length=len(data)):
                with self.assertRaises(wm.WatermarkError):
                    wm.mark_image(data, TOKEN, KEY)
        with self.assertRaises(wm.WatermarkError):
            wm.mark_image(good, TOKEN[:-1], KEY)
        with self.assertRaises(wm.WatermarkError):
            wm.mark_image(good, TOKEN, KEY[:-1])
        _, receipt = self.roundtrip(good)
        with self.assertRaises(wm.WatermarkError):
            wm.extract_image(good, KEY, TOKEN, dict(receipt['context'], width=True))

    def test_unsupported_png_modes_and_color_key_do_not_silently_drop_transparency(self):
        for depth, color, interlace in ((16, 6, 0), (8, 3, 0), (8, 6, 1), (8, 0, 0)):
            data = (wm._PNG_MAGIC + chunk(b'IHDR', struct.pack('>IIBBBBB', 32, 24, depth, color, 0, 0, interlace))
                    + chunk(b'IDAT', zlib.compress(bytes(32 * 24 * 4))) + chunk(b'IEND', b''))
            with self.assertRaises(wm.WatermarkError):
                wm.mark_image(data, TOKEN, KEY)
        rgb, _ = png(channels=3)
        with self.assertRaises(wm.WatermarkError):
            wm.mark_image(rgb[:33] + chunk(b'tRNS', bytes(6)) + rgb[33:], TOKEN, KEY)

    def test_a_token_only_in_metadata_is_not_a_watermark(self):
        data, _ = png()
        fake = data[:33] + chunk(b'tEXt', b'Release-ID\0' + TOKEN.hex().encode()) + data[33:]
        _, receipt = self.roundtrip(data)
        self.assertFalse(wm.extract_image(fake, KEY, TOKEN, receipt['context'])['matched'])
        original = gif(local=False)
        fake = original[:-1] + b'!\xfe' + blocks(TOKEN.hex().encode()) + b';'
        _, receipt = self.roundtrip(original)
        self.assertFalse(wm.extract_image(fake, KEY, TOKEN, receipt['context'])['matched'])

    def test_lossy_jpeg_and_palette_requantization_are_not_claimed_supported(self):
        from PySide6.QtCore import QByteArray, QBuffer, QIODevice
        from PySide6.QtGui import QImage
        data, _ = png()
        marked, _ = self.roundtrip(data)
        encoded = QByteArray()
        output = QBuffer(encoded)
        self.assertTrue(output.open(QIODevice.WriteOnly))
        self.assertTrue(QImage.fromData(marked).save(output, 'JPEG', 70))
        with self.assertRaises(wm.WatermarkError):
            wm.extract_image(bytes(encoded), KEY, TOKEN, {})
        # A real JPEG encode/decode back to the supported RGBA PNG container
        # keeps the same public context, but destroys enough actual blue bits.
        decoded = QImage.fromData(bytes(encoded)).convertToFormat(QImage.Format_RGBA8888)
        pixels = bytes(decoded.constBits())
        stride = decoded.width() * 4
        raw = b''.join(b'\0' + pixels[at:at + stride] for at in range(0, len(pixels), stride))
        jpeg_roundtrip = (wm._PNG_MAGIC + chunk(b'IHDR', struct.pack('>IIBBBBB', 32, 24, 8, 6, 0, 0, 0))
                          + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
        context = wm.mark_image(data, TOKEN, KEY)[1]['context']
        lost = wm.extract_image(jpeg_roundtrip, KEY, TOKEN, context)
        self.assertFalse(lost['matched'])
        self.assertGreater(lost['bit_errors'], 0)
        marked, report = self.roundtrip(gif(local=False))
        reduced = bytearray(marked)
        for start, end in wm._Gif(marked).palette_ranges:
            reduced[start:end] = reduced[start:end].translate(MASK_LOW_BIT)
        result = wm.extract_image(bytes(reduced), KEY, TOKEN, report['context'])
        self.assertFalse(result['matched'])
        self.assertGreater(result['bit_errors'], 0)

    def test_actual_five_049_release_assets_lossless_roundtrip_and_scope(self):
        names = ('assembly-depth-review049.png', 'assembly-six-depth049.png',
                 'gpu-six-depth049.png', 'gpu-insertion049.gif', 'gpu-insertion-six049.gif')
        rows = []
        directory = os.environ.get('DS_IMAGE_WATERMARK_QA_DIR')
        destination = Path(directory) if directory else None
        if destination:
            destination.mkdir(parents=True, exist_ok=False)
        source_hash = hashlib.sha256((ROOT / 'image_watermark050.py').read_bytes()).hexdigest()
        test_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        for name in names:
            with self.subTest(asset=name):
                path = ROOT / 'assets/showcase' / name
                before = path.read_bytes()
                cpu = time.process_time()
                marked, report = self.roundtrip(before)
                mark_and_extract_cpu = time.process_time() - cpu
                start = time.perf_counter()
                decoded = compare_decoded(before, marked)
                decode_seconds = time.perf_counter() - start
                extracted = wm.extract_image(marked, KEY, TOKEN, report['context'])
                self.assertFalse(wm.extract_image(before, KEY, TOKEN, report['context'])['matched'])
                self.assertFalse(wm.extract_image(marked, bytes(reversed(KEY)), TOKEN, report['context'])['matched'])
                self.assertFalse(wm.extract_image(marked, KEY, b'wrong-token!', report['context'])['matched'])
                self.assertEqual(path.read_bytes(), before)
                if before.startswith(wm._PNG_MAGIC):
                    stripped = png_without_metadata(marked)
                    self.assertTrue(wm.extract_image(stripped, KEY, TOKEN, report['context'])['matched'])
                tracemalloc.start()
                traced_result = wm.extract_image(marked, KEY, TOKEN, report['context'])
                traced_retained, traced_peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                self.assertTrue(traced_result['matched'])
                row = dict(name=name, source_sha256=hashlib.sha256(before).hexdigest(),
                           marked_sha256=hashlib.sha256(marked).hexdigest(),
                           input_bytes=len(before), output_bytes=len(marked), embedding=report,
                           extraction=extracted, independent_decode=decoded,
                           mark_and_extract_cpu_seconds=mark_and_extract_cpu,
                           independent_decode_wall_seconds=decode_seconds,
                           allocation_scope=dict(operation='Actual marked asset extraction only',
                           retained_traced_bytes=traced_retained, peak_traced_bytes=traced_peak,
                           excludes='Preexisting input/output buffers, embedding, Qt decode, allocator RSS and whole application'),
                           negative_controls=['unmarked', 'wrong_key', 'wrong_token'])
                rows.append(row)
                if destination:
                    with (destination / ('marked-' + name)).open('xb') as stream:
                        stream.write(marked)
        # Allocation scope is separately measured on a small synthetic sample;
        # never relabel it as the real application's RSS or the five assets.
        sample, _ = png(width=128, height=128)
        tracemalloc.start()
        marked, report = wm.mark_image(sample, TOKEN, KEY)
        wm.extract_image(marked, KEY, TOKEN, report['context'])
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(hashlib.sha256((ROOT / 'image_watermark050.py').read_bytes()).hexdigest(), source_hash)
        self.assertEqual(hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), test_hash)
        if destination:
            receipt = dict(source_sha256=source_hash, test_sha256=test_hash,
                           synthetic_public_fixture_key=True, publisher_secret_used=False,
                           native=False, gl=False, gui_window=False, hardware=False, network=False,
                           rows=rows, allocation_scope=dict(fixture='128x128 RGBA PNG mark+extract',
                           retained_traced_bytes=retained, peak_traced_bytes=peak,
                           application_rss_measured=False),
                           limitations=['PNG only8-bit non-interlaced RGB/RGBA withouttRNS/APNG',
                           'GIF palette entries are carriers; actual index usage is not decoded by codec',
                           'Only lossless original carriers/metadata removal are guaranteed',
                           'JPEG unsupported; requantized GIF demonstrably loses token',
                           'External signed manifest authenticates token; this codec is not ownership proof'])
            with (destination / 'report.json').open('x', encoding='utf-8') as stream:
                json.dump(receipt, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
        self.assertEqual(len(rows), 5)


if __name__ == '__main__':
    unittest.main()
