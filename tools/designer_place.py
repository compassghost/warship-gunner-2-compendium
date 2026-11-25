"""Run the game's own placement check (0x19d008, errors 1-8) in the emulator for the mounts of a DAT 26 design, in the order the screen re-validates them (0x19c328):
clear the voxel volume, then for every mount: err = 0x19d008(mount, 0); when err == 0 stamp it (0x19d098) so later mounts collide with it.
  python tools/designer_place.py            -> error histogram over the 530 stock designs
Work struct (base B = *(gp - 0x4c6c)): +4 shape table (DSN 37 raw), +0x44 hull zone grid (160 x 85), +0x3568 hull table INDEX, +0x3e15 voxel volume (0x3080 bytes cleared... see 0x19d070),
+0x47bd4 + 0x12 i mount i (x, level, y, part table index (u16s at 0 / 2 / 4 / 6), b8, barrels-1, b12, b13, b14, b15 (pair role), +0xe error, +0xf carried, +0x10 state), +0x482dc mount count.
"""
import os, sys, struct, json
sys.path.insert(0, os.path.dirname(__file__))
import designer_emu as DE, designer_vp as V
import wg2

B = 0x1400000
SHAPES = 0x1600000
M0 = 0x47bd4

def make():
    c = DE.make_cpu()
    f = open(os.path.join(DE.ROOT, 'iso_extract/DSN.BIN'), 'rb'); idx = wg2.read_index(f); o, n = idx[37]; f.seek(o)
    c.put(SHAPES, f.read(n))
    c.wr(DE.GP - 0x4c6c, 4, B); c.wr(B + 4, 4, SHAPES)
    c.wr(0x70000000, 4, 0x70000010)
    c.hooks[0x254e58] = lambda cpu: setattr(cpu, 'bad', True) or cpu.r.__setitem__(2, 0)
    c.hooks[0x254e88] = lambda cpu: cpu.r.__setitem__(2, 0)
    c.hooks[0x254da0] = lambda cpu: cpu.r.__setitem__(2, 0)
    # part table index by id
    T = V.Tables(); c.T = T
    c.pidx = {}
    base = c.tab['part']
    for i in range(1120): c.pidx[struct.unpack_from('<I', c.get(base + 144 * i, 4))[0] if False else c.rd(base + 144 * i, 4)] = i
    c.hullidx = {}
    for i in range(145): c.hullidx[c.rd(c.tab['hull'] + 40 * i, 2)] = i
    return c

def load(c, d, grid=None):
    """Put design d (2048 bytes) into the work struct. grid = 160 x 85 hull zone bytes (rows) or None (zeros)."""
    hid = struct.unpack_from('<H', d, 0x1a)[0]
    c.wr(B + 0x3568, 4, c.hullidx[hid])
    if grid is not None: c.put(B + 0x44, b''.join(bytes(r) for r in grid))
    ms = list(V.mounts(d)); c.wr(B + 0x482dc, 4, len(ms))
    for i, m in enumerate(ms):
        a = B + M0 + 0x12 * i
        c.put(a, bytes(0x12))
        c.wr(a, 2, m['x']); c.wr(a + 2, 2, m['level']); c.wr(a + 4, 2, m['y']); c.wr(a + 6, 2, c.pidx[m['id']])
        c.wr(a + 8, 1, m['b8']); c.wr(a + 9, 1, m['barrels'] - 1); c.wr(a + 0xa, 1, m['mag']); c.wr(a + 0xb, 1, m['b13']); c.wr(a + 0xc, 1, m['b14']); c.wr(a + 0xd, 1, m['b15'])
    return ms

def validate(c, d, grid=None):
    ms = load(c, d, grid)
    c.run(0x19d070, ())          # clear volume
    errs = []
    for i, m in enumerate(ms):
        a = B + M0 + 0x12 * i
        e = c.run(0x19d008, (a, 0)) & 0xffffffff
        errs.append(e)
        if e == 0: c.run(0x19d098, (a, i, 0))
    return errs

if __name__ == '__main__':
    import collections
    c = make(); b = V._dat(26); H = None
    from designer_voxels import hull_grid
    grids = {}; hist = collections.Counter(); ex = {}
    for k in range(530):
        d = b[2048 * k:2048 * (k + 1)]; hid = struct.unpack_from('<H', d, 0x1a)[0]; pic = c.T.hulls[hid][0][5] & 255
        if pic not in grids: grids[pic] = hull_grid(pic)
        errs = validate(c, d, grids[pic])
        for i, e in enumerate(errs):
            hist[e] += 1
            if e and e not in ex: ex[e] = (k, i)
    print('error histogram over all stock mounts:', dict(hist)); print('first examples (design, mount):', ex)
