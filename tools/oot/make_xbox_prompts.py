# Button-prompt overlay for Ocarina (Switch 2 build, Nin_Ounce_NVN2): the A and B, and the X and Y prompts swapped, for
# pad_layout = xbox_prompts (runtime/romfs.c overlay_init loads romfs-patches-xbox next to romfs-index.bin).
#
# The glyph, BNTX and CFF routines are adapted from tools/make_romfs_patches.py (itself adapted from MacNativeGames
# games/totk/scripts/make_romfs_patches.py, MIT, Copyright (c) 2026 MacNativeGames contributors).
#
# That layout plays an Xbox pad by position, as nintendo does: the right button, labelled B, does Switch A. The prompts
# should then name the label, so what the game draws for A and B (X and Y) is exchanged. Built from the game's own data on
# the player's own copy; nothing is added and the output is derived from the game: never commit or share it.
#   - Font2/Scalable/External.Nin_Ounce_NVN2.bfotf.zs: the button glyphs U+E040 A, U+E041 B, U+E042 X, U+E043 Y (the text of
#     every prompt: LayoutMsg/DoCommand_00.msbt T_KeyA_00.. and the message bodies use them). CFF outlines and horizontal
#     metrics swapped.
#   - UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.bntx.zs: the images KeyTexFontA/B/X/Y_00 (64x64 BC4) and
#     OcarinaButtonA/B/X/Y_00 (ocarina notes), swapped pair by pair; each pair has the same format, size and tiling.
# Not covered: the Chinese fonts FZLTHB and FZLTZHB (TrueType) also hold U+E040..E043; zh-CN/zh-TW keep the Switch letters.
#
# Input: build/romfs (romfs.bin and index.json). Output: build/oot111/romfs-patches-xbox/<path> and manifest.tsv
# (path, size, SHA-256 of the file, SHA-256 of the original), checked at start by the runtime. Run with the embedded Python
# (ferramentas\python\python.exe, 3.14: compression.zstd), no other packages.
import argparse
import compression.zstd as zstd
import hashlib
import json
import os
import struct
from pathlib import Path

root = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser(description='Build romfs-patches-xbox: the A/B and X/Y button prompts of Ocarina swapped.')
ap.add_argument('--romfs', type=Path, default=root / 'build' / 'romfs', help='folder with romfs.bin and index.json')
ap.add_argument('--out', type=Path, default=root / 'build' / 'oot111' / 'romfs-patches-xbox')
ap.add_argument('--level', type=int, default=12, help='zstd level of the recompressed files (the BNTX is 244 MB)')
args = ap.parse_args()

FONT = 'Font2/Scalable/External.Nin_Ounce_NVN2.bfotf.zs'
BNTX = 'UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.bntx.zs'
KEY_GLYPHS = ((0xE040, 0xE041), (0xE042, 0xE043))   # A B, X Y
KEY_TEXTURES = (('KeyTexFontA_00', 'KeyTexFontB_00'), ('KeyTexFontX_00', 'KeyTexFontY_00'),
                ('OcarinaButtonA_00', 'OcarinaButtonB_00'), ('OcarinaButtonX_00', 'OcarinaButtonY_00'))

index = json.loads((args.romfs / 'index.json').read_text())
assert index['status'] == 'pass', 'build/romfs/index.json is not a verified extraction'
files = {f['path']: f for f in index['files']}


def sarc_members(data):
    assert data[:4] == b'SARC' and data[6:8] == b'\xff\xfe'
    header, size, start = struct.unpack_from('<HxxII', data, 4)
    assert size == len(data) and data[header:header + 4] == b'SFAT'
    count = struct.unpack_from('<H', data, header + 6)[0]
    names = header + 12 + count * 16
    assert data[names:names + 4] == b'SFNT'
    names += 8
    out = {}
    for i in range(count):
        _, attribute, lo, hi = struct.unpack_from('<4I', data, header + 12 + i * 16)
        offset = names + (attribute & 0xffffff) * 4
        out[data[offset:data.index(0, offset, start)].decode()] = (start + lo, start + hi)
    return out


def bntx_swap(data, pairs):
    """Swap the image data of each (name, name) pair of textures in the BNTX data (a bytearray). Both of a pair must
    have the same header from flags to layout (format, size, tiling, mips) and image size, so the bytes of one are a
    valid image of the other."""
    assert data[:4] == b'BNTX' and data[0x20:0x24] in (b'NX  ', b'Ounc'), data[:0x24]
    count, table = struct.unpack_from('<IQ', data, 0x24)
    found = {}
    for k in range(count):
        info = struct.unpack_from('<Q', data, table + 8 * k)[0]
        assert data[info:info + 4] == b'BRTI'
        name = struct.unpack_from('<Q', data, info + 0x60)[0]
        name = data[name + 2:name + 2 + struct.unpack_from('<H', data, name)[0]].decode().split('^')[0]
        mips = struct.unpack_from('<Q', data, info + 0x70)[0]
        shape = bytes(data[info + 0x10:info + 0x3c]) + bytes(data[info + 0x50:info + 0x54])
        found[name] = (shape, struct.unpack_from('<Q', data, mips)[0], struct.unpack_from('<I', data, info + 0x50)[0])
    for a, b in pairs:
        assert a in found and b in found, f'{a} or {b} missing from the texture list'
        (shape_a, at_a, size), (shape_b, at_b, _) = found[a], found[b]
        assert shape_a == shape_b, f'{a} and {b} differ in format, size or tiling'
        data[at_a:at_a + size], data[at_b:at_b + size] = data[at_b:at_b + size], data[at_a:at_a + size]
    return found


def cff_index(data, pos):
    count = struct.unpack_from('>H', data, pos)[0]
    if not count:
        return [], 0, pos + 2
    size = data[pos + 2]
    offsets = [int.from_bytes(data[pos + 3 + i * size:pos + 3 + (i + 1) * size], 'big') for i in range(count + 1)]
    first = pos + 2 + (count + 1) * size
    return [(first + offsets[i], first + offsets[i + 1]) for i in range(count)], size, first + offsets[-1]


def cff_charstrings(data, cff):
    """The offset (from the CFF table) of the CharStrings INDEX: operator 17 of the Top DICT. CID-keyed fonts are refused."""
    _, _, pos = cff_index(data, cff + data[cff + 2])
    top, _, _ = cff_index(data, pos)
    (pos, end), operands, found = top[0], [], None
    while pos < end:
        b = data[pos]
        if b <= 21:
            op = (12, data[pos + 1]) if b == 12 else b
            pos += 2 if b == 12 else 1
            assert op != (12, 30), 'CID-keyed CFF'
            if op == 17:
                found = operands[-1]
            operands = []
        elif b == 28:
            operands.append(struct.unpack_from('>h', data, pos + 1)[0]); pos += 3
        elif b == 29:
            operands.append(struct.unpack_from('>i', data, pos + 1)[0]); pos += 5
        elif b == 30:
            pos += 1
            while data[pos] & 0x0f != 0x0f and data[pos] & 0xf0 != 0xf0:
                pos += 1
            pos += 1
            operands.append(0)
        elif b <= 246:
            operands.append(b - 139); pos += 1
        elif b <= 250:
            operands.append((b - 247) * 256 + data[pos + 1] + 108); pos += 2
        else:
            operands.append(-(b - 251) * 256 - data[pos + 1] - 108); pos += 2
    assert found is not None, 'no CharStrings in the Top DICT'
    return found


def otf_glyph(data, cmap, code):
    for k in range(struct.unpack_from('>H', data, cmap + 2)[0]):
        platform, encoding, offset = struct.unpack_from('>HHI', data, cmap + 4 + 8 * k)
        p = cmap + offset
        if (platform, encoding) != (3, 1) or struct.unpack_from('>H', data, p)[0] != 4:
            continue
        seg = struct.unpack_from('>H', data, p + 6)[0] // 2
        for s in range(seg):
            end = struct.unpack_from('>H', data, p + 14 + 2 * s)[0]
            start = struct.unpack_from('>H', data, p + 16 + 2 * seg + 2 * s)[0]
            if not start <= code <= end:
                continue
            delta = struct.unpack_from('>h', data, p + 16 + 4 * seg + 2 * s)[0]
            at = p + 16 + 6 * seg + 2 * s
            ro = struct.unpack_from('>H', data, at)[0]
            glyph = code if not ro else struct.unpack_from('>H', data, at + ro + 2 * (code - start))[0]
            return (glyph + delta) & 0xffff if glyph else 0
    raise AssertionError(f'U+{code:04X} is not in the font')


def otf_checksum(data):
    data = bytes(data) + bytes(-len(data) % 4)
    return sum(struct.unpack(f'>{len(data) // 4}I', data)) & 0xffffffff


def bfotf_decode(data):
    """(plain bytearray, key): a BFOTF is an OpenType font after an 8-byte header; from offset 4 on, every 4-byte word is
    XORed with one key, which the size field gives away (it holds the font's length)."""
    key = bytes(x ^ y for x, y in zip(data[4:8], struct.pack('>I', len(data) - 8)))
    return bytearray(data[:4]) + bytearray(x ^ key[i % 4] for i, x in enumerate(data[4:])), key


def bfotf_swap(data, pairs):
    """The BFOTF data with the glyphs of each (code point, code point) pair swapped: CFF outlines and horizontal metrics,
    then the table checksums."""
    plain, key = bfotf_decode(data)
    font = plain[8:]
    assert font[:4] == b'OTTO', 'not a CFF OpenType font'
    tables = {}
    for k in range(struct.unpack_from('>H', font, 4)[0]):
        tag, _, offset, length = struct.unpack_from('>4sIII', font, 12 + 16 * k)
        tables[tag] = (12 + 16 * k, offset, length)
    cff = tables[b'CFF '][1]
    strings, size, end = cff_index(font, cff + cff_charstrings(font, cff))
    hmtx, metrics = tables[b'hmtx'][1], struct.unpack_from('>H', font, tables[b'hhea'][1] + 34)[0]
    order = list(range(len(strings)))
    for a, b in pairs:
        ga, gb = otf_glyph(font, tables[b'cmap'][1], a), otf_glyph(font, tables[b'cmap'][1], b)
        assert 0 < ga < len(strings) and 0 < gb < len(strings) and ga < metrics and gb < metrics, (a, b, ga, gb)
        order[ga], order[gb] = order[gb], order[ga]
        ma, mb = hmtx + 4 * ga, hmtx + 4 * gb
        font[ma:ma + 4], font[mb:mb + 4] = font[mb:mb + 4], font[ma:ma + 4]
    body = b''.join(bytes(font[slice(*strings[g])]) for g in order)
    first = strings[0][0]
    assert first + len(body) == end
    font[first:end] = body
    at, base = first - (len(strings) + 1) * size, 1
    for i, g in enumerate(order + [None]):
        font[at + i * size:at + (i + 1) * size] = base.to_bytes(size, 'big')
        if g is not None:
            base += strings[g][1] - strings[g][0]
    head = tables[b'head'][1]
    struct.pack_into('>I', font, head + 8, 0)
    for entry, offset, length in tables.values():
        struct.pack_into('>I', font, entry + 4, otf_checksum(font[offset:offset + length]))
    struct.pack_into('>I', font, head + 8, (0xb1b0afba - otf_checksum(font)) & 0xffffffff)
    plain[8:] = font
    return bytes(plain[:4]) + bytes(x ^ key[i % 4] for i, x in enumerate(plain[4:]))


def glyph_outline(data, code):
    """The CharString bytes of the glyph of a code point in the BFOTF data."""
    font = bfotf_decode(data)[0][8:]
    tables = {}
    for k in range(struct.unpack_from('>H', font, 4)[0]):
        tag, _, offset, length = struct.unpack_from('>4sIII', font, 12 + 16 * k)
        tables[tag] = offset
    cff = tables[b'CFF ']
    strings, _, _ = cff_index(font, cff + cff_charstrings(font, cff))
    lo, hi = strings[otf_glyph(font, tables[b'cmap'], code)]
    return bytes(font[lo:hi])


with (args.romfs / 'romfs.bin').open('rb') as image:
    def read(path):
        f = files[path]
        image.seek(f['offset'])
        b = image.read(f['size'])
        assert len(b) == f['size']
        return b
    dictionaries = {}
    pack = zstd.decompress(read('Pack/ZsDic.pack.zs'))
    for name, (lo, hi) in sarc_members(pack).items():
        d = zstd.ZstdDict(pack[lo:hi])
        dictionaries[d.dict_id] = d
    originals = {path: read(path) for path in (FONT, BNTX)}


def unpack(path):
    raw = originals[path]
    frame = zstd.get_frame_info(raw)
    return zstd.decompress(raw, zstd_dict=dictionaries.get(frame.dictionary_id)), frame.dictionary_id


def pack_zs(path, contents):
    raw = originals[path]
    frame = zstd.get_frame_info(raw)
    dictionary = dictionaries.get(frame.dictionary_id)
    workers = max(1, min(8, (os.cpu_count() or 2) - 1))
    options = {zstd.CompressionParameter.compression_level: args.level, zstd.CompressionParameter.nb_workers: workers}
    data = zstd.compress(contents, options=options, zstd_dict=dictionary)
    assert zstd.decompress(data, zstd_dict=dictionary) == contents
    assert zstd.get_frame_info(data).dictionary_id == frame.dictionary_id
    return data


outputs = {}
font, _ = unpack(FONT)
swapped_font = bfotf_swap(font, KEY_GLYPHS)
for a, b in KEY_GLYPHS:   # the outline of each glyph is now the other's
    assert glyph_outline(swapped_font, a) == glyph_outline(font, b) and glyph_outline(swapped_font, b) == glyph_outline(font, a)
    assert glyph_outline(font, a) != glyph_outline(font, b), 'the two glyphs are the same drawing'
outputs[FONT] = swapped_font

bntx, _ = unpack(BNTX)
original_bntx = bytes(bntx)
bntx = bytearray(bntx)
found = bntx_swap(bntx, KEY_TEXTURES)
for a, b in KEY_TEXTURES:
    (_, at_a, size), (_, at_b, _) = found[a], found[b]
    assert bntx[at_a:at_a + size] == original_bntx[at_b:at_b + size] and bntx[at_b:at_b + size] == original_bntx[at_a:at_a + size]
    assert original_bntx[at_a:at_a + size] != original_bntx[at_b:at_b + size], f'{a} and {b} hold the same image'
assert sum(x != y for x, y in zip(bntx, original_bntx)) <= 2 * sum(found[n][2] for pair in KEY_TEXTURES for n in pair)
outputs[BNTX] = bytes(bntx)

lines = []
for path, contents in outputs.items():
    data = pack_zs(path, contents)
    target = args.out / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    lines.append('\t'.join([path, str(len(data)), hashlib.sha256(data).hexdigest(), hashlib.sha256(originals[path]).hexdigest()]))
(args.out / 'manifest.tsv').write_text('# path\tsize\tsha256\toriginal_sha256 (tools/oot/make_xbox_prompts.py)\n'
                                       + ''.join(line + '\n' for line in lines))
print(json.dumps(dict(status='pass', out=str(args.out), glyphs=KEY_GLYPHS, textures=KEY_TEXTURES, files=list(outputs))))
