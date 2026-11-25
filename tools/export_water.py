"""Export the game's sea textures (MAP.BIN entries 1-14, 128 x 128 tiles that repeat) for the model viewer's water option.

MAP.BIN opens with five groups of three entries: a 16 KB colour block (not a picture: probably a fog / water colour ramp) and two sea tiles.
Entries 10 and 11 are the clear blue sea, 5 / 8 / 14 darker blue, 2 grey-teal, 1 / 4 / 7 (the same picture) rough grey, 13 a grey rock-like tile.
Which weather or time of day uses which one was not worked out, so the viewer offers a few of them by look.
Output: web/models/water_<entry>.png.   Run: python tools/export_water.py"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import extract_minimaps as em, model_entities as me
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/models')

if __name__ == '__main__':
    M = me.Arc('MAP')
    for e in (1, 2, 5, 8, 10, 11, 14):
        data = em.texture(M.get(e))
        open(os.path.join(OUT, 'water_%d.png' % e), 'wb').write(data)
        print('water_%d.png' % e, len(data))
