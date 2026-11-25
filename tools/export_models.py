"""Export decoded PSC1 models for the web model viewer.
web/models/<archive>_<entry>.bin = for each part: Float32 x,y,z per vertex (node transforms of the rest pose applied), Uint16 a,b,c,e per quad,
                                   Uint16 u0,v0..u3,v3 per quad (counts in web/models/index.json; a face without texture has all-zero UVs);
web/models/<archive>_<entry>.png = the model's texture, taken from the game's model resource table (tools/model_entities.py), not from the neighbouring entry;
web/models/index.json            = id, archive, entry, internal name, category, entity names, parts (slot, kind, counts, untextured faces), texture entry.
Run: python tools/export_models.py [min_vertices]     (default 1 = every model with geometry; needs no third-party packages)"""
import os, sys, json, struct, math, zlib
sys.path.insert(0, os.path.dirname(__file__))
import wg2, psc1, model_entities, model_fixes
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/models'); os.makedirs(OUT, exist_ok=True)
minv = int(sys.argv[1]) if len(sys.argv) > 1 else 1
ARCS = ('CHR', 'MDT_SHIP', 'MDT_WEPH', 'MDT_WEPL')
# hand fixes for single models: see tools/model_fixes.py

from pngutil import png_from_rgba as png      # an indexed (palette) PNG when the picture has <= 256 colours (the game's textures do): same pixels, about 27% smaller

def texture(d):
    """SHTXFS (12-byte header, log2 size in bytes 10-11) or SHTXST (8-byte header, size from the data length) -> PNG bytes or None."""
    if d[:6] == b'SHTXFS': w, h = 1 << d[10], 1 << d[11]; hdr = 12
    elif d[:6] == b'SHTXST':
        hdr = 8; n = len(d) - 8 - 1024; s = int(math.isqrt(n))
        w, h = (s, s) if s * s == n else (int(math.isqrt(n // 2)) * 2, int(math.isqrt(n // 2)))
        if w * h != n: return None
    else: return None
    pal = d[hdr:hdr + 1024]; data = d[hdr + 1024:hdr + 1024 + w * h]
    if len(data) != w * h: return None
    st = d[:6] == b'SHTXST'          # SHTXST alpha is 0..128 (PS2 range), SHTXFS alpha is 0..255
    P = [bytes((pal[4 * i + 2], pal[4 * i + 1], pal[4 * i], min(255, pal[4 * i + 3] * 2 - (1 if pal[4 * i + 3] else 0)) if st else pal[4 * i + 3])) for i in range(256)]
    return png(w, h, b''.join(P[p] for p in data))

ents = {m['id']: m for m in model_entities.build()}
arcs = {a: model_entities.Arc(a) for a in model_entities.MODEL_ARCS}
texcache = {}
def tex_png(ref):
    ref = tuple(ref)
    if ref not in texcache:
        try: texcache[ref] = texture(arcs[ref[0]].get(ref[1]))
        except Exception: texcache[ref] = None
    return texcache[ref]

index = []
for arc in ARCS:
    A = arcs[arc]
    for e in range(len(A.idx)):
        name = f'{arc.lower()}_{e}'; info = ents.get(name)
        if not info: continue
        try: model = psc1.parse_model(A.get(e))
        except Exception as ex: print('parse failed', name, ex); continue
        parts = [p for p in model['parts'] if p['quads']]
        if not parts or max(len(p['verts']) for p in parts) < minv: continue
        model_fixes.apply(model, parts)      # hand fixes (root-flagged nodes that should follow their parent)
        blob = bytearray(); meta = []
        for p in parts:
            blob += struct.pack('<%df' % (3 * len(p['verts'])), *[c for v in p['verts'] for c in v])
            blob += struct.pack('<%dH' % (4 * len(p['quads'])), *[c for q in p['quads'] for c in q])
            blob += struct.pack('<%dH' % (8 * len(p['uvs'])), *[c for u in p['uvs'] for c in u])
            meta.append(dict(slot=p['slot'], v=len(p['verts']), q=len(p['quads']), kind=p['kind'], untex=sum(1 for u in p['uv_index'] if u is None),
                             nodes=sum(1 for n in p['nodes'] if n['verts'][1] > n['verts'][0])))
        open(os.path.join(OUT, name + '.bin'), 'wb').write(blob)
        tex = None
        if info['texture']:
            data = tex_png(info['texture'])
            if data: open(os.path.join(OUT, name + '.png'), 'wb').write(data); tex = info['texture'][1]
        if tex is None and os.path.exists(os.path.join(OUT, name + '.png')): os.remove(os.path.join(OUT, name + '.png'))     # stale texture from the old neighbour rule
        V = parts[0]['verts']; bb = [max(v[a] for v in V) - min(v[a] for v in V) for a in range(3)]
        index.append(dict(id=name, archive=arc, entry=e, name=model['name'], variant=('Dock' if arc.startswith('MDT') and model['name'].endswith('H') else 'In-game' if arc.startswith('MDT') and model['name'].endswith('L') else ''), cat=info['category'], cls=model_entities.klass(model['name'], info['entities']), desc=info['description'], ents=info['entities'] or info['entities_inferred'],
                          inferred=not info['entities'] and bool(info['entities_inferred']), parts=meta, size=[round(x) for x in bb], tex=tex,
                          tex_arc=info['texture'][0] if tex is not None else None))
json.dump(index, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf8'), separators=(',', ':'), ensure_ascii=False)
print(len(index), 'models;', sum(1 for m in index if m['tex'] is not None), 'with a texture;', sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) // 1024, 'KB')
