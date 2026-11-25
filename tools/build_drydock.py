"""Build the drydock composites for the model viewer from MAP.BIN (decoded 2026-11-15, see notes/drydock.md).

MAP.BIN entries 787-802 are eight drydocks, DOCK00 .. DOCK07 (map table records 67-73 + 66): for each, entry 787 + 2n is the map mesh (PSM0) and entry 788 + 2n is the same dock as a
PSC1 model. The two have the same extent (the PSM0 float coordinates x 4096 = the PSC1 vertex units) and nearly the same vertices (PSM0 has ~3% more), so the PSC1 is used here: the
existing psc1.py parser reads it. The docks are upgrade stages: DOCK00 is the smallest (3,404 faces), DOCK07 the biggest (5,651): "fully built" = DOCK07 (an assumption: the file
does not say which stage is which; the face counts and sizes only grow).
All eight share one set of eight 256 x 256 texture atlases (MAP entries 803-810, the map record's tile list). A PSC1 face selects its atlas with the low three bits of the last byte of
its UV record's attribute bytes (values seen 0-4; bit 6 is another flag): this was checked by eye, not from the game code.
The composite splits each dock by atlas into parts (the viewers draw one texture per part), "texid" = dock_tile_<k> (web/models/dock_tile_<k>.png).
Writes web/models/composite_drydock_<n>.bin, the atlases, and returns the entries for tools/build_composite.py to merge into composites.json.
Run: python tools/build_drydock.py   (normally called by tools/build_composite.py)"""
import os, sys, json, struct, collections
sys.path.insert(0, os.path.dirname(__file__))
import psc1, model_entities as me, extract_minimaps as em
ROOT = os.path.join(os.path.dirname(__file__), '..')
MODELS = os.path.join(ROOT, 'web/models')
TILES = list(range(803, 811))                    # MAP entries of the eight atlases (map table tile ids 804-811 are file ids = entry + 1)

def export_tiles(M):
    for k, e in enumerate(TILES):
        open(os.path.join(MODELS, 'dock_tile_%d.png' % k), 'wb').write(em.texture(M.get(e)))

def build_one(M, n):
    mod = psc1.parse_model(M.get(788 + 2 * n)); slots = {p['slot']: p for p in mod['parts'] if p['quads']}
    part = slots[0]; V = part['verts']; blob = bytearray(); parts = []; col = bytearray()
    WZ = 1986                                                 # slot 1 of every dock PSC1 holds the dock's own water surface: flat faces at z 1986 (all of them in DOCK00 / 01 / 04 / 07), plus a few other faces in some docks
    for slot in (0, 1):
        sp = slots.get(slot)
        if sp is None: continue
        groups = collections.defaultdict(list)
        for k, q in enumerate(sp['quads']):
            ui = sp['uv_index'][k]
            if ui is None: continue
            flat = slot == 1 and all(abs(sp['verts'][i][2] - WZ) < 1 for i in q)
            groups[(sp['uv_attrs'][ui][3] & 7) + (8 if flat else 0)].append(k)              # +8: the flat faces at the basin's water height form their own parts
        for t8 in sorted(groups):
            t = t8 & 7; flat = t8 >= 8; ks0 = groups[t8]
            ks = ks0; used = sorted({i for k in ks for i in sp['quads'][k]}); new = {v: j for j, v in enumerate(used)}
            blob += struct.pack('<%df' % (3 * len(used)), *[c for v in used for c in sp['verts'][v]])
            blob += struct.pack('<%dH' % (4 * len(ks)), *[new[i] for k in ks for i in sp['quads'][k]])
            blob += struct.pack('<%dH' % (8 * len(ks)), *[c for k in ks for c in sp['uvs'][k]])
            for k in ks:                                      # the face's colour (3 bytes, 128 = neutral): the dock has its lighting baked into these, so the dock viewer multiplies the texture by them
                ci = sp['face_colour'][k]; col += bytes(sp['colours'][ci]) if ci < len(sp['colours']) else b'\x80\x80\x80'
            parts.append(dict(slot=len(parts), v=len(used), q=len(ks), kind='mesh', untex=0, nodes=0, texid='dock_tile_%d' % t, label=('Basin water, the game\'s own flat faces (%d)' % len(ks)) if flat else 'Atlas %d (%d faces)%s' % (t, len(ks), ' extra part' if slot == 1 else '')))
    wz = 0                                                    # the open sea around the dock is drawn at z 0 (the piers' decks sit just above it); the basin's own faces sit at WZ
    mid ='composite_drydock_%d' % n; open(os.path.join(MODELS, mid + '.bin'), 'wb').write(blob); open(os.path.join(MODELS, mid + '.col'), 'wb').write(col)
    xs = [v[0] for v in V]; ys = [v[1] for v in V]; zs = [v[2] for v in V]
    full = n == 7
    return dict(id=mid, archive='COMPOSITE', entry=0, name='Dock (Missions %d-%d)' % (n * 6 + 1, n * 6 + 6), variant='', cat='dock', cls='', ents=[], inferred=False, all=True,
                desc='The game\'s floating dock (the story\'s Skidbladnir), MAP.BIN entry %d (DOCK%02d)' % (788 + 2 * n, n),
                boss='', waterZ=wz, colors=mid + '.col', parts=parts, size=[round(max(xs) - min(xs)), round(max(ys) - min(ys)), round(max(zs) - min(zs))], tex=None, tex_arc=None)

def build_one_psm(M, n):
    """Same composite, but from the map mesh (PSM0, entry 787 + 2n) with its own tables: the UV record's byte 8 (low 3 bits) = the atlas, 0-7 (the PSC1 route gave only 0-4)."""
    d = M.get(787 + 2 * n); off = struct.unpack_from('<15I', d, 4); vo, fo, co, uo = off[1], off[2], off[3], off[4]
    nv, nf, nc, nu = [struct.unpack_from('<H', d, o)[0] for o in (vo, fo, co, uo)]
    V = [struct.unpack_from('<3f', d, vo + 2 + i * 16) for i in range(nv)]
    V = [tuple(c * 4096 for c in v) for v in V]
    groups = collections.defaultdict(list)
    for k in range(nf):
        f0, a, b, c, e, flags, ci, ui = struct.unpack_from('<8H', d, fo + 2 + k * 36)
        if ui >= nu or ci >= nc or max(a, b, c, e) >= nv: continue
        ur = d[uo + 2 + ui * 12: uo + 2 + ui * 12 + 12]
        groups[ur[8] & 7].append((a, b, c, e, ur[:8], bytes(d[co + 2 + ci * 3: co + 5 + ci * 3])))
    blob = bytearray(); parts = []; col = bytearray()
    for t in sorted(groups):
        fs = groups[t]; used = sorted({i for f in fs for i in f[:4]}); new = {v: j for j, v in enumerate(used)}
        blob += struct.pack('<%df' % (3 * len(used)), *[x for v in used for x in V[v]])
        blob += struct.pack('<%dH' % (4 * len(fs)), *[new[i] for f in fs for i in f[:4]])
        blob += struct.pack('<%dH' % (8 * len(fs)), *[x * 64 for f in fs for x in f[4]])
        for f in fs: col += f[5]
        parts.append(dict(slot=len(parts), v=len(used), q=len(fs), kind='mesh', untex=0, nodes=0, texid='dock_tile_%d' % t, label='Atlas %d (%d faces)' % (t, len(fs))))
    mid = 'composite_drydock_%d' % n; open(os.path.join(MODELS, mid + '.bin'), 'wb').write(blob); open(os.path.join(MODELS, mid + '.col'), 'wb').write(col)
    xs = [v[0] for v in V]; ys = [v[1] for v in V]; zs = [v[2] for v in V]
    return dict(id=mid, archive='COMPOSITE', entry=0, name='Dock (Missions %d-%d)' % (n * 6 + 1, n * 6 + 6), variant='', cat='dock', cls='', ents=[], inferred=False, all=True,
                desc='The game\'s floating dock (the story\'s Skidbladnir), MAP.BIN entry %d (DOCK%02d)' % (787 + 2 * n, n),
                boss='', waterZ=0, colors=mid + '.col', parts=parts, size=[round(max(xs) - min(xs)), round(max(ys) - min(ys)), round(max(zs) - min(zs))], tex=None, tex_arc=None)

def build_all():
    M = me.Arc('MAP'); export_tiles(M)
    out = [(build_one if os.environ.get('DOCK_PSC1') else build_one_psm)(M, n) for n in range(8)]      # the map mesh (PSM0) is the default: its own UV records name the atlas; set DOCK_PSC1=1 for the old PSC1 route
    for e in out: print(e['id'], e['name'], [p['q'] for p in e['parts']], 'size', e['size'])
    return out

if __name__ == '__main__':
    build_all()
