"""Offline, bounded RGB watermarks for original PNG/GIF release artifacts.

The 96-bit release token is authenticated outside this codec.  Nothing here
identifies a user, contacts a service, opens Qt, or runs in a paint/sampler loop.
PNG supports non-interlaced 8-bit RGB/RGBA; GIF changes palette RGB only.  The
carrier survives lossless storage/metadata removal, not arbitrary recoding.
Private keys never appear in results.  Callers must preserve unmarked originals.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import struct
import time
import zlib


SCHEME = 'ds-image-lsb-v1'
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_DIMENSION = 8192
MAX_PIXELS = 16 * 1024 * 1024
MAX_DECODED_BYTES = 64 * 1024 * 1024
MAX_GIF_FRAMES = 256
MAX_GIF_FRAME_PIXELS = 128 * 1024 * 1024
MAX_BLOCKS = 262144
_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


class WatermarkError(ValueError):
    """Invalid, unsupported, over-budget, or insufficient-capacity artifact."""


def _credentials(token, key):
    if type(token) is not bytes or len(token) != 12:
        raise WatermarkError('A 12-byte release token is required')
    if type(key) is not bytes or len(key) != 32:
        raise WatermarkError('A 32-byte publisher key is required')


def _size(width, height):
    if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION
            and width * height <= MAX_PIXELS):
        raise WatermarkError('Image dimensions exceed the offline codec limit')


def _repetition(capacity):
    for count in (7, 5, 3):
        if capacity >= 96 * count:
            return count
    raise WatermarkError('Insufficient opaque RGB/palette capacity')


def _chunk(kind, payload):
    return (struct.pack('>I', len(payload)) + kind + payload
            + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff))


class _Png:
    def __init__(self, data):
        self.data = data
        self.chunks = []
        at = 8
        idats = []
        header = None
        ended = False
        idat_ended = False
        while at < len(data):
            if len(self.chunks) >= 4096 or at + 12 > len(data):
                raise WatermarkError('Invalid PNG chunk table')
            length = struct.unpack_from('>I', data, at)[0]
            end = at + 12 + length
            if end > len(data):
                raise WatermarkError('Truncated PNG chunk')
            kind = data[at + 4:at + 8]
            payload = data[at + 8:end - 4]
            if (len(kind) != 4 or not all(65 <= c <= 90 or 97 <= c <= 122 for c in kind)
                    or zlib.crc32(kind + payload) & 0xffffffff
                    != struct.unpack_from('>I', data, end - 4)[0]):
                raise WatermarkError('Invalid PNG chunk/CRC')
            if not self.chunks and kind != b'IHDR':
                raise WatermarkError('PNG header must be first')
            if kind == b'IHDR':
                if header is not None or length != 13:
                    raise WatermarkError('Invalid PNG header')
                header = struct.unpack('>IIBBBBB', payload)
            elif kind == b'IDAT':
                if idat_ended:
                    raise WatermarkError('Non-consecutive PNG image data')
                idats.append(payload)
            elif idats:
                idat_ended = True
            if kind in (b'acTL', b'fcTL', b'fdAT', b'tRNS'):
                raise WatermarkError('Animated/color-key PNG is unsupported')
            if kind[0] & 32 == 0 and kind not in (b'IHDR', b'IDAT', b'PLTE', b'IEND'):
                raise WatermarkError('Unknown critical PNG chunk')
            self.chunks.append((kind, at, end))
            at = end
            if kind == b'IEND':
                if length or at != len(data):
                    raise WatermarkError('Invalid PNG end')
                ended = True
                break
        if header is None or not idats or not ended:
            raise WatermarkError('Incomplete PNG')
        width, height, depth, color, compression, filtering, interlace = header
        _size(width, height)
        if depth != 8 or color not in (2, 6) or compression or filtering or interlace:
            raise WatermarkError('Only non-interlaced 8-bit RGB/RGBA PNG is supported')
        self.width, self.height, self.color = width, height, color
        self.channels = 3 if color == 2 else 4
        stride = width * self.channels
        expected = (stride + 1) * height
        if expected > MAX_DECODED_BYTES:
            raise WatermarkError('PNG decoded size exceeds limit')
        decoder = zlib.decompressobj()
        try:
            raw = decoder.decompress(b''.join(idats), expected + 1)
        except zlib.error as error:
            raise WatermarkError('Invalid PNG compressed stream') from error
        if (len(raw) != expected or not decoder.eof or decoder.unconsumed_tail
                or decoder.unused_data):
            raise WatermarkError('PNG compressed size/stream mismatch')
        pixels = bytearray(stride * height)
        previous = bytearray(stride)
        for y in range(height):
            start = y * (stride + 1)
            mode = raw[start]
            row = bytearray(raw[start + 1:start + 1 + stride])
            if mode == 1:
                for i in range(self.channels, stride):
                    row[i] = (row[i] + row[i - self.channels]) & 255
            elif mode == 2:
                for i in range(stride):
                    row[i] = (row[i] + previous[i]) & 255
            elif mode in (3, 4):
                for i in range(stride):
                    left = row[i - self.channels] if i >= self.channels else 0
                    up = previous[i]
                    if mode == 3:
                        predictor = (left + up) // 2
                    else:
                        upper_left = previous[i - self.channels] if i >= self.channels else 0
                        p = left + up - upper_left
                        a, b, c = abs(p - left), abs(p - up), abs(p - upper_left)
                        predictor = left if a <= b and a <= c else up if b <= c else upper_left
                    row[i] = (row[i] + predictor) & 255
            elif mode != 0:
                raise WatermarkError('Invalid PNG row filter')
            pixels[y * stride:(y + 1) * stride] = row
            previous = row
        self.pixels = pixels
        self.capacity = (width * height if self.channels == 3
                         else pixels[3::4].count(255))

    def positions(self, ranks):
        if self.capacity == self.width * self.height:
            return {rank: rank * self.channels + 2 for rank in ranks}
        wanted = set(ranks)
        result = {}
        rank = 0
        for pixel, alpha in enumerate(self.pixels[3::4]):
            if alpha == 255:
                if rank in wanted:
                    result[rank] = pixel * 4 + 2
                    if len(result) == len(wanted):
                        break
                rank += 1
        return result

    def context(self):
        return dict(version=1, format='PNG', width=self.width, height=self.height,
                    color_type=self.color, carrier_count=self.capacity,
                    repetition=_repetition(self.capacity))

    def values(self, ranks):
        positions = self.positions(ranks)
        return [self.pixels[positions[rank]] & 1 for rank in ranks]

    def mark(self, ranks, bits):
        positions = self.positions(ranks)
        changed = 0
        for rank, bit in zip(ranks, bits):
            at = positions[rank]
            new = (self.pixels[at] & 254) | bit
            changed += new != self.pixels[at]
            self.pixels[at] = new
        compressor = zlib.compressobj(6)
        stride = self.width * self.channels
        parts = []
        for y in range(self.height):
            parts.append(compressor.compress(b'\0' + self.pixels[y * stride:(y + 1) * stride]))
        parts.append(compressor.flush())
        encoded = b''.join(parts)
        chunks = [_PNG_MAGIC]
        wrote = False
        for kind, start, end in self.chunks:
            if kind == b'IDAT':
                if not wrote:
                    chunks.append(_chunk(b'IDAT', encoded))
                    wrote = True
            else:
                chunks.append(self.data[start:end])
        result = b''.join(chunks)
        if len(result) > MAX_INPUT_BYTES:
            raise WatermarkError('Marked PNG exceeds encoded size limit')
        return result, changed


class _Gif:
    def __init__(self, data):
        self.data = data
        if len(data) < 14:
            raise WatermarkError('Truncated GIF header')
        self.width, self.height = struct.unpack_from('<HH', data, 6)
        _size(self.width, self.height)
        at = 13
        palettes = []
        transparent = set()
        frames = 0
        frame_pixels = 0
        pending_transparency = None
        blocks = 0

        def table(offset, flags):
            count = 1 << ((flags & 7) + 1)
            if offset + count * 3 > len(data):
                raise WatermarkError('Truncated GIF palette')
            palettes.append((offset, count))
            return len(palettes) - 1, offset + count * 3

        def subblocks(offset):
            nonlocal blocks
            while True:
                if offset >= len(data) or blocks >= MAX_BLOCKS:
                    raise WatermarkError('Invalid GIF subblocks')
                length = data[offset]
                offset += 1
                blocks += 1
                if not length:
                    return offset
                offset += length
                if offset > len(data):
                    raise WatermarkError('Truncated GIF subblock')

        global_table = None
        if data[10] & 128:
            global_table, at = table(at, data[10])
        ended = False
        while at < len(data):
            blocks += 1
            if blocks > MAX_BLOCKS:
                raise WatermarkError('GIF block count exceeds limit')
            tag = data[at]
            at += 1
            if tag == 0x3b:
                if at != len(data) or not frames:
                    raise WatermarkError('Invalid GIF trailer')
                ended = True
                break
            if tag == 0x21:
                if at >= len(data):
                    raise WatermarkError('Truncated GIF extension')
                label = data[at]
                at += 1
                if label == 0xf9:
                    if at + 6 > len(data) or data[at] != 4 or data[at + 5] != 0:
                        raise WatermarkError('Invalid GIF graphic control')
                    pending_transparency = data[at + 4] if data[at + 1] & 1 else None
                    at += 6
                else:
                    # Plain-text rendering consumes its pending control too.
                    if label == 0x01:
                        if (global_table is None or at >= len(data) or data[at] != 12
                                or at + 13 > len(data)):
                            raise WatermarkError('Invalid GIF plain-text header/palette')
                        if pending_transparency is not None:
                            if pending_transparency >= palettes[global_table][1]:
                                raise WatermarkError('GIF text transparent index exceeds palette')
                            transparent.add((global_table, pending_transparency))
                        pending_transparency = None
                    at = subblocks(at)
                continue
            if tag != 0x2c or at + 9 > len(data):
                raise WatermarkError('Invalid GIF image descriptor')
            left, top, width, height, flags = struct.unpack_from('<HHHHB', data, at)
            at += 9
            _size(width, height)
            frames += 1
            frame_pixels += width * height
            if (left + width > self.width or top + height > self.height
                    or frames > MAX_GIF_FRAMES or frame_pixels > MAX_GIF_FRAME_PIXELS):
                raise WatermarkError('GIF frame dimensions/count exceed limit')
            palette = global_table
            if flags & 128:
                palette, at = table(at, flags)
            if palette is None or at >= len(data) or not 2 <= data[at] <= 8:
                raise WatermarkError('GIF image palette/LZW header is invalid')
            if pending_transparency is not None:
                if pending_transparency >= palettes[palette][1]:
                    raise WatermarkError('GIF transparent index exceeds palette')
                transparent.add((palette, pending_transparency))
            pending_transparency = None
            at = subblocks(at + 1)
        if not ended:
            raise WatermarkError('Incomplete GIF')
        groups = {}
        for palette, (start, count) in enumerate(palettes):
            for index in range(count):
                offset = start + index * 3
                rgb = data[offset:offset + 3]
                canonical = tuple(value >> 1 for value in rgb)
                row = groups.setdefault(canonical, {'colors': set(), 'offsets': [], 'transparent': False})
                row['colors'].add(rgb)
                row['offsets'].append(offset)
                row['transparent'] |= (palette, index) in transparent
        # Duplicate exact colors are one logical carrier and change together.
        # Ambiguous high-seven-bit colors and any transparent group stay intact.
        self.groups = [tuple(row['offsets']) for _, row in sorted(groups.items())
                       if len(row['colors']) == 1 and not row['transparent']]
        self.capacity = len(self.groups) * 3
        self.frames = frames
        self.palette_count = len(palettes)
        self.skipped_groups = len(groups) - len(self.groups)
        self.palette_ranges = tuple((start, start + count * 3) for start, count in palettes)

    def context(self):
        return dict(version=1, format='GIF', width=self.width, height=self.height,
                    frame_count=self.frames, carrier_count=self.capacity,
                    repetition=_repetition(self.capacity))

    def values(self, ranks):
        return [self.data[self.groups[rank // 3][0] + rank % 3] & 1 for rank in ranks]

    def mark(self, ranks, bits):
        result = bytearray(self.data)
        changed = 0
        samples = 0
        for rank, bit in zip(ranks, bits):
            changed += (self.data[self.groups[rank // 3][0] + rank % 3] & 1) != bit
            for start in self.groups[rank // 3]:
                at = start + rank % 3
                new = (result[at] & 254) | bit
                samples += new != result[at]
                result[at] = new
        self.changed_palette_bytes = samples
        return bytes(result), changed


def _image(data):
    if type(data) is not bytes or not 0 < len(data) <= MAX_INPUT_BYTES:
        raise WatermarkError('Image input size/type exceeds limit')
    if data.startswith(_PNG_MAGIC):
        return _Png(data)
    if data.startswith((b'GIF87a', b'GIF89a')):
        return _Gif(data)
    raise WatermarkError('Only PNG/GIF release images are supported')


def _context_bytes(context):
    return json.dumps(context, sort_keys=True, separators=(',', ':')).encode('ascii')


def _plan(key, context):
    domain = SCHEME.encode() + b'\0' + _context_bytes(context)
    capacity = context['carrier_count']
    count = 96 * context['repetition']
    selected, used = [], set()
    counter = 0
    # Rejection sampling, including rejection of duplicate carrier ranks.
    limit = (1 << 64) - ((1 << 64) % capacity)
    while len(selected) < count:
        if counter >= 65536:
            raise WatermarkError('Keyed carrier selection exceeds work budget')
        block = hmac.new(key, domain + b'/positions/' + struct.pack('>I', counter), hashlib.sha256).digest()
        counter += 1
        for at in range(0, 32, 8):
            value = int.from_bytes(block[at:at + 8], 'big')
            if value >= limit:
                continue
            rank = value % capacity
            if rank not in used:
                used.add(rank)
                selected.append(rank)
                if len(selected) == count:
                    break
    whitening = hmac.new(key, domain + b'/payload', hashlib.sha256).digest()[:12]
    return selected, whitening


def _bits(raw):
    return [(value >> bit) & 1 for value in raw for bit in range(7, -1, -1)]


def _report(image, context, started):
    count = 96 * context['repetition']
    result = dict(scheme=SCHEME, format=context['format'], context=context,
                  payload_bits=96, carrier_count=image.capacity,
                  repetition=context['repetition'], used_carriers=count,
                  coverage=count / image.capacity, alpha_changed=False,
                  elapsed_seconds=time.perf_counter() - started,
                  robustness='Original/lossless bytes and metadata removal; lossy recoding is not guaranteed.')
    if isinstance(image, _Gif):
        result.update(frame_count=image.frames, palette_count=image.palette_count,
                      skipped_palette_groups=image.skipped_groups,
                      palette_usage_verified=False, indices_and_animation_unchanged=True)
    return result


def mark_image(data: bytes, token: bytes, key: bytes):
    """Return new image bytes plus a public, secret-free embedding receipt."""
    started = time.perf_counter()
    _credentials(token, key)
    image = _image(data)
    context = image.context()
    ranks, whitening = _plan(key, context)
    payload = _bits(bytes(a ^ b for a, b in zip(token, whitening)))
    bits = payload * context['repetition']
    marked, changed = image.mark(ranks, bits)
    report = _report(image, context, started)
    report.update(changed_carriers=changed,
                  changed_rgb_samples=getattr(image, 'changed_palette_bytes', changed),
                  max_delta=int(bool(changed)), bit_errors=0)
    return marked, report


def extract_image(data: bytes, key: bytes, expected_token: bytes, context):
    """Read RGB carriers and compare against an externally authenticated token.

    ``context`` is the public mark receipt's context, not embedded metadata.
    It is checked against the actual image before keyed carrier selection.
    """
    started = time.perf_counter()
    _credentials(expected_token, key)
    image = _image(data)
    actual = image.context()
    if (type(context) is not dict or len(context) != len(actual)
            or any(type(v) not in (int, str) for v in context.values())
            or context != actual):
        raise WatermarkError('Public image context does not match the artifact')
    ranks, whitening = _plan(key, actual)
    raw = image.values(ranks)
    repeat = actual['repetition']
    majority = [int(sum(raw[r * 96 + bit] for r in range(repeat)) > repeat // 2)
                for bit in range(96)]
    decoded = bytes(sum(majority[at + bit] << (7 - bit) for bit in range(8))
                    for at in range(0, 96, 8))
    recovered = bytes(a ^ b for a, b in zip(decoded, whitening))
    expected_bits = _bits(bytes(a ^ b for a, b in zip(expected_token, whitening))) * repeat
    report = _report(image, actual, started)
    report.update(matched=hmac.compare_digest(recovered, expected_token),
                  recovered_token_hex=recovered.hex(),
                  bit_errors=sum((a ^ b).bit_count() for a, b in zip(recovered, expected_token)),
                  raw_bit_errors=sum(a != b for a, b in zip(raw, expected_bits)))
    return report
