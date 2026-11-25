"""3D occupancy model of the design screen (decoded from 0x19d098 stamp, 0x19cdc0 collision test, 0x19c968 hull-mask test, 0x19d800 picking):
each mount occupies the voxels (x + col, level + a_row, y + b_row) for which the magazine/side shape A (part u16[13 + b12], rotation 0, flip x if b13) has bit (a_row, col)
AND the picture/plan shape B (part u16[7 + barrels - 1], rotated by facing(b13, b14)) has bit (b_row, col) on the same column.
Voxel index in the game's volume: y * 5280 + level * 160 + x (+ 0x3e15), 160 x 33 x 48.
Hull mask grid (DSN 39 stream, 160 x 85 bytes): side-view cells at row = level + a_row, plan-view cells at row = 33 + y + b_row; a set bit of shape A must lie on a side cell, a set bit of shape B on a plan cell,
whose byte AND part byte 0xb (u16[5] >> 8) is non-zero.
  python tools/designer_voxels.py   -> collision / mask self-check on the 530 game designs
"""
import os, sys, struct, json
sys.path.insert(0, os.path.dirname(__file__))
import designer_vp as V

def flip_bits(row, w):
    return int(format(row, '032b')[:w][::-1].ljust(32, '0'), 2)

def transformed(T, idx, rot, flag):
    """shape record after 0x1a5bc0: (w, h, rows[]) -- bit (31 - col) of rows[r] set = cell (col, r). rot 0..3 clockwise, flag 1 flip y, 2 flip x."""
    s = T.shape(idx); w, h = s['w'], s['h']
    cells = {(c, r) for r in range(h) for c in range(w) if s['rows'][r] >> (31 - c) & 1}
    if rot == 1:   cells = {(h - 1 - r, c) for c, r in cells}; w, h = h, w
    elif rot == 2: cells = {(w - 1 - c, h - 1 - r) for c, r in cells}
    elif rot == 3: cells = {(r, w - 1 - c) for c, r in cells}; w, h = h, w
    if flag & 1: cells = {(c, h - 1 - r) for c, r in cells}
    if flag & 2: cells = {(w - 1 - c, r) for c, r in cells}
    return w, h, cells

def voxels(T, m):
    p = T.parts[m['id']]
    ai, bi = p[13 + m['mag']], p[7 + m['barrels'] - 1]
    if ai >= 907 or bi >= 907: return set()
    _, _, A = transformed(T, ai, 0, 2 if m['b13'] else 0)
    r, f = V.facing(m['b13'], m['b14'])
    _, _, B = transformed(T, bi, r, f)
    out = set()
    for (ca, ra) in A:
        for (cb, rb) in B:
            if ca == cb: out.add((m['x'] + ca, m['level'] + ra, m['y'] + rb))
    return out

def hull_grid(i, hulls_json=os.path.join(os.path.dirname(__file__), '../web/designer_sprites/hulls.json')):
    """160 x 85 zone-byte grid of hull picture i (from the run-length lists of web/designer_sprites/hulls.json)."""
    H = json.load(open(hulls_json))['hulls']
    g = [[0] * 160 for _ in range(85)]
    for r, runs in enumerate(H[i]['grid']):
        for v, c, n in runs:
            for k in range(n): g[r][c + k] = v
    return g

def mask_ok(T, m, g):
    """0x19c968: only the BOX region (after rotation / flip) of the shapes is tested. Side: shape A cells at grid row level + row; plan: shape B cells at row 33 + y + row;
    each cell's zone byte AND part byte 0xb (u16[5] >> 8) must be non-zero (side test skipped when part u16[6] & 0x80)."""
    p = T.parts[m['id']]; zm = p[5] >> 8
    ai, bi = p[13 + m['mag']], p[7 + m['barrels'] - 1]
    if ai >= 907 or bi >= 907: return 0          # 65535 = no such shape (not tested)
    _, _, A = transformed(T, ai, 0, 2 if m['b13'] else 0)
    r, f = V.facing(m['b13'], m['b14']); _, _, B = transformed(T, bi, r, f)
    _, _, ax0, ay0, abw, abh = V.rotate_box(T.shape(ai), 0, 2 if m['b13'] else 0)
    _, _, bx0, by0, bbw, bbh = V.rotate_box(T.shape(bi), r, f)
    def cell(row, col): return g[row][col] if 0 <= row < 85 and 0 <= col < 160 else 0
    if not p[6] & 0x80:
        for c, rr in A:
            if ax0 <= c < ax0 + (abw or 99) and ay0 <= rr < ay0 + (abh or 99) and not cell(m['level'] + rr, m['x'] + c) & zm: return 5
    for c, rr in B:
        if bx0 <= c < bx0 + (bbw or 99) and by0 <= rr < by0 + (bbh or 99) and not cell(33 + m['y'] + rr, m['x'] + c) & zm: return 6
    return 0

if __name__ == '__main__':
    T = V.Tables(); b = V._dat(26)
    grids = {}; bad = n = 0
    for k in range(530):
        d = b[2048 * k:2048 * (k + 1)]; hid = struct.unpack_from('<H', d, 0x1a)[0]; pic = T.hulls[hid][0][5] & 255
        if pic not in grids: grids[pic] = hull_grid(pic)
        for m in V.mounts(d):
            n += 1; bad += mask_ok(T, m, grids[pic]) != 0
    print('hull-mask failures (errors 5 / 6) over all game mounts: %d of %d' % (bad, n))
    coll = pairs = nodata = 0; worst = []
    for k in range(530):
        d = b[2048 * k:2048 * (k + 1)]
        occ = {}; n = 0
        for i, m in enumerate(V.mounts(d)):
            for v in voxels(T, m):
                if v in occ: n += 1
                occ[v] = i
        coll += n
        if n: worst.append((n, k))
    print('voxel overlaps over all game designs:', coll, 'in', len(worst), 'designs; worst', sorted(worst)[-5:])
