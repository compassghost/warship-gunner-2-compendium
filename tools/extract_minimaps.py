"""Extract the mission minimaps from MAP.BIN into web/maps/.

DAT entry 4 is the map table: 74 records x 40 bytes, starting at byte 612 (dat_tables.arrays). Each record is
  u16 x2  = model file ids of the map mesh (PSM0) and its object model (PSC1)     [file id = archive base + entry + 1]
  u16 x8  = terrain tile textures (SHTXST)
  u16 x3  = minimap images: (1) coastline silhouette, (2) shaded relief with grid, (3) grid-only 256 x 256 sheet
  then floats / flags.
Open-sea maps share one blank minimap set (records pointing at the same ids). The first records (0-12) store their minimap as SHTXST
images; the rest are SHTXFS.
Output: web/maps/map_<entry>.png (one per MAP entry used) and web/maps/maps.json = [{"rec": n, "images": [entry, entry, entry]}].
No third-party packages needed."""
import os, sys, json, struct, math, zlib
sys.path.insert(0, os.path.dirname(__file__))
import model_entities as me, dat_tables
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/maps'); os.makedirs(OUT, exist_ok=True)

from pngutil import png_from_rgba as png      # an indexed (palette) PNG when the picture has <= 256 colours: same pixels, smaller (the dock tiles and sea textures in web/models come through here too)

def texture(d):
    if d[:6] == b'SHTXFS': w, h = 1 << d[10], 1 << d[11]; hdr = 12
    elif d[:6] == b'SHTXST':
        hdr = 8; n = len(d) - 8 - 1024; s = int(math.isqrt(n))
        w, h = (s, s) if s * s == n else (int(math.isqrt(n // 2)) * 2, int(math.isqrt(n // 2)))
        if w * h != n: return None
    else: return None
    pal = d[hdr:hdr + 1024]; data = d[hdr + 1024:hdr + 1024 + w * h]
    if len(data) != w * h: return None
    st = d[:6] == b'SHTXST'
    P = [bytes((pal[4 * i + 2], pal[4 * i + 1], pal[4 * i], min(255, pal[4 * i + 3] * 2 - (1 if pal[4 * i + 3] else 0)) if st else pal[4 * i + 3])) for i in range(256)]
    return png(w, h, b''.join(P[p] for p in data))

if __name__ == '__main__':
    D = me.Arc('DAT').get(4); M = me.Arc('MAP'); A = dat_tables.arrays(D)
    recs, done = [], {}
    for k in range(len(A) - 1):                                   # the last array is a different (44-byte) record
        r = struct.unpack_from('<20H', D, A[k]['offset'])
        imgs = []
        for fid in r[10:13]:
            if not fid: continue
            e = fid - 1
            if e not in done:
                data = texture(M.get(e)); done[e] = data is not None
                if data: open(os.path.join(OUT, 'map_%d.png' % e), 'wb').write(data)
            if done[e]: imgs.append(e)
        recs.append(dict(rec=k, images=imgs))
    json.dump(recs, open(os.path.join(OUT, 'maps.json'), 'w'), separators=(',', ':'))
    print(len(recs), 'map records;', sum(done.values()), 'minimap images written to web/maps')
