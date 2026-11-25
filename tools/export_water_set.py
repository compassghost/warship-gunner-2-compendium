"""Export the game's sea tile sets for the smooth water generator (web/water.html, web/water.js).

MAP.BIN opens with five groups of three entries (see tools/export_water.py):
    entry 3g     16 KB block = 16 alternate 256-colour palettes (1,024 bytes each, B G R A order, 4,096 colours in all)
    entry 3g+1   tile A: 128 x 128 (the last group: 128 x 64) 8-bit indexed SHTXFS texture with its own palette (the "rough" / highlight layer)
    entry 3g+2   tile B: the same, softer base layer
Decoded 2026-11-15: applying the 16 block palettes to a tile's index image gives 16 colour variants (blue-grey, dusk brown, night dark ...), so the game recolours the
sea by palette (time of day / weather), it does not store a picture per variant. Which map record uses which variant was not found.

Output (web/water/):
  idx_<entry>.png   the tile's INDEX image: R = palette index (alpha 255), so a shader can look the colour up itself and filter after the lookup (no banding)
  pal_<group>.png   256 x 18 RGBA: row 0 = tile A's own palette, row 1 = tile B's own palette, rows 2-17 = the 16 block palettes
  water.json        groups: id, entries, tile sizes, palette row names
Run: python tools/export_water_set.py"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import model_entities as me
from PIL import Image
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/water'); os.makedirs(OUT, exist_ok=True)

def tile(d):
    w, h = 1 << d[10], 1 << d[11]
    return w, h, d[12:12 + 1024], d[12 + 1024:12 + 1024 + w * h]

def palette_rows(blob):
    """BGRA bytes -> list of 256 (r, g, b, 255) (the game's alpha channel is ignored: it is 0 in places on purpose-less entries)."""
    return [(blob[4 * i + 2], blob[4 * i + 1], blob[4 * i], 255) for i in range(len(blob) // 4)]

if __name__ == '__main__':
    M = me.Arc('MAP'); groups = []
    for g in range(5):
        ramp = M.get(3 * g); ea, eb = 3 * g + 1, 3 * g + 2
        wa, ha, pa, ia = tile(M.get(ea)); wb, hb, pb, ib = tile(M.get(eb))
        for e, w, h, idx in ((ea, wa, ha, ia), (eb, wb, hb, ib)):
            im = Image.new('RGBA', (w, h)); im.putdata([(v, 0, 0, 255) for v in idx]); im.save(os.path.join(OUT, 'idx_%d.png' % e))
        rows = [palette_rows(pa), palette_rows(pb)] + [palette_rows(ramp[k * 1024:(k + 1) * 1024]) for k in range(16)]
        pim = Image.new('RGBA', (256, 18)); pim.putdata([c for r in rows for c in r]); pim.save(os.path.join(OUT, 'pal_%d.png' % g))
        groups.append(dict(id=g, a=dict(entry=ea, w=wa, h=ha), b=dict(entry=eb, w=wb, h=hb), rows=['tile A own palette', 'tile B own palette'] + ['block palette %d' % k for k in range(16)]))
        print('group', g, 'tiles', (wa, ha), (wb, hb))
    json.dump(groups, open(os.path.join(OUT, 'water.json'), 'w'), indent=1)
