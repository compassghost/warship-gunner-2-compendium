"""Export the dock scenery placements (found 2026-11-16) from the dock map meshes (PSM0, MAP.BIN entry 787 + 2n) to web/models/dock_objects.json.

The table is header section [12] of the PSM0 (header offset list index 12): u16 count (288), u16 0, then 28-byte rows:
  f32 x, y, z (PSM0 float units: 1 = 4096 model units)  +  u32 id  +  u32 flag  +  u32 extra  +  u32 0.
Rows 0-24, 224-225 and 256-287 are other markers (bounds, camera / water / path points) and are not exported.
Object rows are 100-257 with flag 1 (or 2) and id = (variant << 16) | (1000 + DOCKJ number): the low 16 bits are 1000 + the DOCKJ model number
(DOCKJ00 .. DOCKJ61 = CHR entries 420 ..), the high 16 bits (0-6) are probably a facing / variant (not decoded).
Which models a dock loads is also visible in MCB1.BLN (block ids 0x8000 + counter; see notes/drydock.md); the DOCKJ numbers there match the table.
Run: python tools/build_dock_objects.py"""
import os, sys, json, struct, re
sys.path.insert(0, os.path.dirname(__file__))
import model_entities as me, bev_script
ROOT = os.path.join(os.path.dirname(__file__), '..')

def rows(M, n):
    d = M.get(787 + 2 * n); off = struct.unpack_from('<15I', d, 4)
    a = off[12]; cnt = struct.unpack_from('<H', d, a)[0]; out = []
    for i in range(cnt):
        x, y, z = struct.unpack_from('<3f', d, a + 4 + i * 28)
        ident, flag, extra, _ = struct.unpack_from('<4I', d, a + 4 + i * 28 + 12)
        out.append((i, x, y, z, ident, flag, extra))
    return out

if __name__ == '__main__':
    M = me.Arc('MAP'); idx = json.load(open(os.path.join(ROOT, 'web/models/index.json'), encoding='utf-8'))
    chr_of = {m['name']: m['id'] for m in idx if m['name'].startswith('DOCKJ')}
    res = {}
    for n in range(8):
        objs = []
        for i, x, y, z, ident, flag, extra in rows(M, n):
            k = ident & 0xffff
            if i < 100 or i > 257 or flag not in (1, 2) or not (1000 <= k <= 1070): continue
            objs.append(dict(row=i, model=chr_of.get('DOCKJ%02d' % (k - 1000)), j=k - 1000, v=ident >> 16, flag=flag, x=round(x, 4), y=round(y, 4), z=round(z, 4)))
        # spawn records of the dock's BEV script (BEV 90 + n): 12-byte header 0a 0s 00 00 | 24 00 00 00 | 44 11 00 00, then f32 x, y, z, rx, ry, rz (radians), type (10.0 or 20.0), f32 0, u32 -1.
        # Object type -> model is INFERRED: type 10 = DOCKJ41 (the AA mount: loaded by every dock, in no id row; the spawns lie on the hull and platform decks), type 20 = DOCKJ20 (loaded, in no id row; two of its spawns coincide with rows 256-257 whose next field is 0x140000).
        bev = bev_script.get(90 + n); trucks = 0
        for m in re.finditer(rb'\x0a[\x00-\x0f]\x00\x00\x24\x00\x00\x00\x44\x11\x00\x00', bev):
            x, y, z, rx, ry, rz, typ = struct.unpack_from('<7f', bev, m.end())
            # type 20 = the pier crane pair; the crane model is the one the dock's MCB block loads: docks 0-3 DOCKJ20 (small harbour crane), 4-5 DOCKJ16, 6-7 DOCKJ15 (tower cranes with the tan tapered tower)
            mode = struct.unpack_from('<I', bev, m.end() + 32)[0]                # 1 = static, 4 = moving (a path follows): the two moving ones are the TRUCKS
            if mode == 4:
                j = (19, 22, 23)[trucks % 3]; trucks += 1                          # DOCKJ19 tarp truck, DOCKJ22 flatbed, DOCKJ23 a third variant (loaded by every dock, no row): which spawn uses which variant is a guess
            else:
                j = {10: 41, 20: 20 if n < 4 else 16 if n < 6 else 15}.get(round(typ))
            if j is None: continue
            objs.append(dict(row=-1, model=chr_of['DOCKJ%02d' % j], j=j, v=0, flag=1, x=round(x, 4), y=round(y, 4), z=round(z, 4), yaw=round(rz, 4), type=round(typ), moving=int(mode == 4), guess=1))
        res[str(n)] = objs
        print('DOCK%02d' % n, len(objs), 'objects,', len({o['j'] for o in objs}), 'kinds')
    json.dump(res, open(os.path.join(ROOT, 'web/models/dock_objects.json'), 'w'), separators=(',', ':'))
