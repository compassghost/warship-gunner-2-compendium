"""Vital-part length (VP%) of a design, decoded from the game's design screen (SLUS_213.87 0x19b650) and checked against the VP% stored in every DAT 26 design (+0x678).

Decoded (see notes/designer_code.md):
 * Shape table = DSN.BIN entry 37 (raw): 907 records x 0x88 bytes: [0] width, [1] height, [4] box x0, [5] box y0, [6] box w, [7] box h, [8..] 32 u32 row bitmaps (MSB = column 0).
 * Part record (DAT 7, 144 B) u16[7..10] = picture shape (index = barrels-1), u16[13..16] = magazine ("vital box") shape (index = mount byte b12, the magazine depth variant).
 * A mount counts when 0x286700 says vital: part byte4 == 1 (weapons) -> u16[68] bit 0 set (all guns / torpedo / missile records have it, CIWS and machine guns too); byte4 == 2 -> part kind in {12, 13, 19, 27}; byte4 == 3 -> always.
 * Pass 1: magazine shape, rotation 0, flag 2 (flip x) if b13 != 0; lo = x + box_x0, hi = lo + (box_w or w) - 1.
   Pass 2: picture shape rotated by 1a5b70(b13, b14): lo2 = x + box_x0'; hi2 = lo(pass 1) + (box_w' or w').
   span = max(hi) - min(lo) + 1; VP% = trunc(span * 100.0 / hull_length), hull_length = hull record byte 0xb.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
import wg2
ROOT = os.path.join(os.path.dirname(__file__), '..')

def _dat(i):
    f = open(os.path.join(ROOT, 'iso_extract/DAT.BIN'), 'rb'); idx = wg2.read_index(f); o, s = idx[i]; f.seek(o)
    return wg2.decompress(f.read(s))[0]

class Tables:
    def __init__(self):
        f = open(os.path.join(ROOT, 'iso_extract/DSN.BIN'), 'rb'); idx = wg2.read_index(f); o, n = idx[37]; f.seek(o)
        self.shapes = f.read(n)
        h = _dat(7)
        self.parts = {}                       # id -> u16[72]
        for i in range(1120):
            u = struct.unpack_from('<72H', h, 144 * i); self.parts[u[0]] = u
        d8 = _dat(8)
        self.hulls = {}
        for i in range(145):
            u = struct.unpack_from('<20H', d8, 40 * i); self.hulls[u[0]] = (u, d8[40 * i + 11])   # byte 0xb = hull length in cells
        self.armor = [struct.unpack_from('<3I', d8, 0x16a8 + 12 * i) for i in range((len(d8) - 0x16a8) // 12)]
        self.curve = struct.unpack('<257H', _dat(10))
    def shape(self, i):
        b = self.shapes[i * 136:(i + 1) * 136]
        return dict(w=b[0], h=b[1], x0=b[4], y0=b[5], bw=b[6], bh=b[7], rows=list(struct.unpack_from('<32I', b, 8)))

def rotate_box(s, rot, flag):
    """Box part of 0x1a5bc0: returns (w, h, x0, y0, bw, bh) after rotation (0, 90, 180, 270 clockwise) and flip flags (1 = flip y, 2 = flip x)."""
    w, h, x0, y0, bw, bh = s['w'], s['h'], s['x0'], s['y0'], s['bw'], s['bh']
    if rot == 1:   w, h, x0, y0, bw, bh = h, w, h - (y0 + bh), x0, bh, bw
    elif rot == 2: x0, y0 = w - (x0 + bw), h - (y0 + bh)
    elif rot == 3: w, h, x0, y0, bw, bh = h, w, y0, w - (x0 + bw), bh, bw
    if flag & 1: y0 = h - (y0 + bh)
    if flag & 2: x0 = w - (x0 + bw)
    return w, h, x0, y0, bw, bh

def facing(b13, b14):
    """0x1a5b70 -> (rotation, flag)"""
    if b13: return 2, 0
    if b14 == 1: return 0, 1
    if b14 == 2: return 3, 0
    return (1 if b14 == 3 else 0), 0

def is_vital(T, pid):
    p = T.parts[pid]; b4 = p[2] & 255
    if b4 == 1: return bool(p[68] & 1)
    if b4 == 2: return (p[3] & 255) in (12, 13, 19, 27)
    return b4 == 3

def mounts(d):
    n = struct.unpack_from('<I', d, 0x660)[0]
    for i in range(n):
        m = d[0x20 + 16 * i:0x30 + 16 * i]
        pid, x, z, y = struct.unpack_from('<HHHH', m, 0)[0], struct.unpack_from('<H', m, 4)[0], struct.unpack_from('<H', m, 6)[0], struct.unpack_from('<H', m, 8)[0]
        yield dict(id=struct.unpack_from('<I', m, 0)[0], x=x, level=z, y=y, mag=m[0xc], barrels=m[0xb] + 1, b8=m[0xa], b13=m[0xd], b14=m[0xe], b15=m[0xf])

def vital_span(T, d):
    lo_all, hi_all = 160, 0
    for m in mounts(d):
        p = T.parts[m['id']]
        if not is_vital(T, m['id']): continue
        mi = p[13 + m['mag']]; pi = p[7 + m['barrels'] - 1]
        w, h, x0, y0, bw, bh = rotate_box(T.shape(mi), 0, 2 if m['b13'] else 0)
        lo = m['x'] + x0; hi = lo + (bw or w) - 1
        r, f = facing(m['b13'], m['b14'])
        w2, h2, x02, y02, bw2, bh2 = rotate_box(T.shape(pi), r, f)
        hi2 = lo + (bw2 or w2)
        lo_all = min(lo_all, lo, m['x'] + x02); hi_all = max(hi_all, hi, hi2)
    return lo_all, hi_all

def vp_percent(T, d):
    hid = struct.unpack_from('<H', d, 0x1a)[0]
    L = T.hulls[hid][1]
    lo, hi = vital_span(T, d)
    if hi < lo: return 0
    return int((hi - lo + 1) * 100.0 / L)

if __name__ == '__main__':
    T = Tables()
    b = _dat(26); ok = bad = 0
    for k in range(len(b) // 2048):
        d = b[2048 * k:2048 * (k + 1)]
        stored = struct.unpack_from('<h', d, 0x678)[0]; mine = vp_percent(T, d)
        if stored == mine: ok += 1
        else:
            bad += 1
            if bad < 15: print('design', k, 'stored', stored, 'computed', mine)
    print('VP%% match: %d / %d' % (ok, ok + bad))
