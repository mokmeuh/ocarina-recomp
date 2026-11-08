# Button-prompt overlay for Ocarina (Switch 2 build, Nin_Ounce_NVN2): the action prompt's face-button diamond redrawn for an
# Xbox pad, for pad_layout = xbox_prompts (runtime/romfs.c overlay_init loads romfs-patches-xbox next to romfs-index.bin).
#
# With that layout the buttons are played by their Xbox names: the bottom button (A) does the game's A, the right one (B)
# the game's B, the left one (X) the game's X, the top one (Y) the game's Y. The letters the game draws are right as they
# are (A stays A); what is wrong is where the Switch puts them: A right, B bottom, X top, Y left. This overlay moves the
# positions, A <-> B and X <-> Y, and leaves every letter alone. Built from the game's own data on the player's own copy;
# nothing is added and the output is derived from the game: never commit or share it.
#
# What encodes the position, in UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.blarc.zs, layout DoCommand_00 (four
# identical copies in the archive; the archive's member names are cut, so they are found by their first characters):
#   - the pane records (BFFH, 68 bytes each, from RootPane on, in the order of the names of the string pool): translation
#     (x, y) at +36 and +40, scale at +24 and +28, parent index at +48. Each of the four variants N_A_00, N_B_00, N_X_00 and
#     N_Y_00 (the prompt of that button) holds the highlighted button N_Btn<L>_00 and the three other buttons as panes
#     P_<letter>_<n>, one on each arm of the diamond at (+-80, 0) and (0, +-80). The Switch has A right, B bottom, X top,
#     Y left; the Xbox has A bottom, B right, X left, Y top: every one of those four positions (x, y) becomes (-y, -x).
#   - the picture behind them, a silhouette of the three circles that are not the highlighted one: the BC4 textures
#     DoCommandCrossBase_A_00 (no circle at the right) and DoCommandCrossBase_B_00 (none at the bottom), with their gradient
#     DoCommandCrossBaseGrd_*, bound by name in the first material of each variant. X reuses _B with the picture's scale y
#     at -1 (no circle at the top) and Y reuses _A with the scale x at -1 (none at the left). The textures of A and B, and
#     of X and Y (with their scales), are exchanged so that the silhouette follows the highlighted button.
# Not covered: the ocarina notes (PaOcarinaSingleNote_00) are a column by pitch, not a diamond; the controller picture
# (PaSystemController_00) and the button-letter glyphs and textures are left as the game has them.
#
# Input: build/romfs (romfs.bin and index.json). Output: build/oot111/romfs-patches-xbox/<path> and manifest.tsv
# (path, size, SHA-256 of the file, SHA-256 of the original), checked at start by the runtime. Run with the embedded Python
# (ferramentas\python\python.exe, 3.14: compression.zstd), no other packages.
import argparse
import compression.zstd as zstd
import hashlib
import json
import os
import re
import shutil
import struct
from pathlib import Path

root = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser(description='Build romfs-patches-xbox: the action prompt diamond of Ocarina laid out as an Xbox pad.')
ap.add_argument('--romfs', type=Path, default=root / 'build' / 'romfs', help='folder with romfs.bin and index.json')
ap.add_argument('--out', type=Path, default=root / 'build' / 'oot111' / 'romfs-patches-xbox')
ap.add_argument('--level', type=int, default=12, help='zstd level of the recompressed archive')
args = ap.parse_args()

BLARC = 'UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.blarc.zs'
LAYOUT = 'DoCommand_00'
VARIANTS = 'ABXY'

index = json.loads((args.romfs / 'index.json').read_text())
assert index['status'] == 'pass', 'build/romfs/index.json is not a verified extraction'
files = {f['path']: f for f in index['files']}


def sarc_nodes(data):
    """(name, start, end) of every SARC member, in SFAT order."""
    assert data[:4] == b'SARC' and data[6:8] == b'\xff\xfe'
    header, size, start = struct.unpack_from('<HxxII', data, 4)
    assert size == len(data) and data[header:header + 4] == b'SFAT'
    count = struct.unpack_from('<H', data, header + 6)[0]
    names = header + 12 + count * 16
    assert data[names:names + 4] == b'SFNT'
    names += 8
    out = []
    for i in range(count):
        _, attribute, lo, hi = struct.unpack_from('<4I', data, header + 12 + i * 16)
        offset = names + (attribute & 0xffffff) * 4
        out.append((data[offset:data.index(0, offset, start)].decode(), start + lo, start + hi))
    return out


def is_float(word, lo, hi):
    f = struct.unpack('<f', struct.pack('<I', word))[0]
    return f == f and lo <= f <= hi


def pane_record_ok(m, o, i):
    w = struct.unpack_from('<17I', m, o)
    return (is_float(w[6], -20, 20) and is_float(w[7], -20, 20) and is_float(w[9], -6000, 6000) and is_float(w[10], -6000, 6000)
            and is_float(w[13], 0, 6000) and is_float(w[14], 0, 6000) and w[6] != 0 and w[7] != 0
            and (w[12] == 0xffffffff or w[12] < i))


def find_panes(m):
    """(offset of the first pane record, number of records): the longest run of 68-byte records whose first has no parent."""
    best = (0, 0)
    for o in range(0x100, min(len(m) - 68 * 4, 0x4000), 4):
        if struct.unpack_from('<I', m, o + 48)[0] != 0xffffffff or not pane_record_ok(m, o, 0):
            continue
        k = 0
        while o + 68 * (k + 1) <= len(m) and pane_record_ok(m, o + 68 * k, k):
            k += 1
        if k > best[1]:
            best = (o, k)
    return best


def string_pool(m):
    """[(offset, string)] of the null-terminated strings from the layout's name on (the pane names come first)."""
    at = m.find(b'RootPane')
    pos = m.rfind(b'\x00', 0, at - 1) + 1
    names = []
    while pos < len(m) and m[pos]:
        end = m.index(b'\x00', pos)
        names.append((pos, m[pos:end].decode()))
        pos = end + 1
    return names


def patch_layout(m):
    """Patch one DoCommand_00 (a bytearray) in place; returns the positions moved."""
    first, count = find_panes(m)
    pool = string_pool(m)
    names = [n for _, n in pool]
    assert names[0] == LAYOUT and names[1] == 'RootPane' and count >= 60, (names[:3], count)
    pane = {names[1 + i]: i for i in range(count)}   # pane name -> record index

    def rec(i):
        return first + 68 * i

    def pos(i):
        return struct.unpack_from('<ff', m, rec(i) + 36)

    moved = {}
    for v in VARIANTS:
        root_i = pane[f'N_{v}_00']
        group = [pane[f'N_Btn{v}_00']] + [i for i in range(count)
                                          if struct.unpack_from('<I', m, rec(i) + 48)[0] == root_i
                                          and re.fullmatch(r'P_[ABXY]_\d\d', names[1 + i])]
        assert len(group) == 4, (v, [names[1 + i] for i in group])
        arms = sorted(tuple(round(c) for c in pos(i)) for i in group)
        assert arms == [(-80, 0), (0, -80), (0, 80), (80, 0)], (v, arms)
        for i in group:
            x, y = pos(i)
            struct.pack_into('<ff', m, rec(i) + 36, -y + 0.0, -x + 0.0)
            moved[names[1 + i]] = (round(x), round(y), round(-y), round(-x))
    # the silhouette: the name pointers (8 bytes, an offset in this member) of the texture bindings, two per name, in the
    # order of the variants A, B, X, Y
    strings = {}
    for hit in re.finditer(rb'[A-Za-z_][A-Za-z0-9_]{3,}(?=\x00)', bytes(m[pool[0][0]:])):
        strings.setdefault(hit.group().decode(), pool[0][0] + hit.start())
    bindings = {}
    for n in ('DoCommandCrossBase_A_00', 'DoCommandCrossBase_B_00', 'DoCommandCrossBaseGrd_A_00', 'DoCommandCrossBaseGrd_B_00'):
        bindings[n] = [o for o in range(0, len(m) - 8, 4) if struct.unpack_from('<Q', m, o)[0] == strings[n]]
        assert len(bindings[n]) == 2, (n, bindings[n])
    (a_cb, y_cb), (b_cb, x_cb) = bindings['DoCommandCrossBase_A_00'], bindings['DoCommandCrossBase_B_00']
    (a_gr, y_gr), (b_gr, x_gr) = bindings['DoCommandCrossBaseGrd_A_00'], bindings['DoCommandCrossBaseGrd_B_00']
    assert a_cb < b_cb < x_cb < y_cb and a_gr < b_gr < x_gr < y_gr, (a_cb, b_cb, x_cb, y_cb)
    for p, q in ((a_cb, b_cb), (x_cb, y_cb), (a_gr, b_gr), (x_gr, y_gr)):   # A <-> B, X <-> Y
        vp, vq = struct.unpack_from('<Q', m, p)[0], struct.unpack_from('<Q', m, q)[0]
        struct.pack_into('<Q', m, p, vq)
        struct.pack_into('<Q', m, q, vp)
    # X and Y: the flip of the silhouette goes with its texture (X: _A flipped at x, Y: _B flipped at y)
    bx, by = rec(pane['P_BaseX_00']), rec(pane['P_BaseY_00'])
    assert struct.unpack_from('<ff', m, bx + 24) == (1.0, -1.0) and struct.unpack_from('<ff', m, by + 24) == (-1.0, 1.0)
    struct.pack_into('<ff', m, bx + 24, -1.0, 1.0)
    struct.pack_into('<ff', m, by + 24, 1.0, -1.0)
    return moved


with (args.romfs / 'romfs.bin').open('rb') as image:
    def read(path):
        f = files[path]
        image.seek(f['offset'])
        b = image.read(f['size'])
        assert len(b) == f['size']
        return b
    dictionaries = {}
    pack = zstd.decompress(read('Pack/ZsDic.pack.zs'))
    for _, lo, hi in sarc_nodes(pack):
        d = zstd.ZstdDict(pack[lo:hi])
        dictionaries[d.dict_id] = d
    original = read(BLARC)

frame = zstd.get_frame_info(original)
dictionary = dictionaries.get(frame.dictionary_id)
plain = zstd.decompress(original, zstd_dict=dictionary)
assert len(plain) == frame.decompressed_size
blarc = bytearray(plain)
copies = [(lo, hi) for name, lo, hi in sarc_nodes(plain) if name.startswith(LAYOUT)]
assert len(copies) == 4 and len({plain[lo:hi] for lo, hi in copies}) == 1, 'DoCommand_00 is expected as four identical copies'
done = None
for lo, hi in copies:
    member = bytearray(plain[lo:hi])
    done = patch_layout(member)
    blarc[lo:hi] = member
changed = [i for i in range(len(plain)) if plain[i] != blarc[i]]
assert changed and all(any(lo <= i < hi for lo, hi in copies) for i in changed), 'bytes outside DoCommand_00 changed'

workers = max(1, min(8, (os.cpu_count() or 2) - 1))
options = {zstd.CompressionParameter.compression_level: args.level, zstd.CompressionParameter.nb_workers: workers}
data = zstd.compress(bytes(blarc), options=options, zstd_dict=dictionary)
assert zstd.decompress(data, zstd_dict=dictionary) == bytes(blarc)
assert zstd.get_frame_info(data).dictionary_id == frame.dictionary_id

if args.out.exists():
    shutil.rmtree(args.out)   # an older build of this folder (it held font and texture files) must not stay
target = args.out / BLARC
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(data)
(args.out / 'manifest.tsv').write_text('# path\tsize\tsha256\toriginal_sha256 (tools/oot/make_xbox_prompts.py)\n'
                                       + '\t'.join([BLARC, str(len(data)), hashlib.sha256(data).hexdigest(),
                                                    hashlib.sha256(original).hexdigest()]) + '\n')
print(json.dumps(dict(status='pass', out=str(args.out), layout_copies=len(copies), changed_bytes=len(changed), moved=done)))
