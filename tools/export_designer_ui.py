"""Export the UI textures used by the design screen / HUD and their sprite rectangle lists to web/designer_sprites/ui/.

Formats (notes/designer_sprites.md):
  texture  = LZ-decoded SHTXFS, 256 x 256 (or 256 x 128) 8bpp, 256-entry BGRA palette (extract_minimaps.texture)
  atlas list = 16-byte records u16 x, y, w, h, u32 0, 80 80 80 80 (a (0,0,0,0) record is an unused slot); rectangles are in texture pixels.
Pairings (rectangles lie inside the opaque pixels of the texture; scored by tools in the session notes): CHR 35 -> CHR 34 (exact, 13 sprites), DSN 34 -> DSN 33 (== DSN 45),
DSN 49 -> DSN 48, DSN 35 -> DSN 32 (guess: eight 64 x 64 tiles of pie wedges).
Output: ui/<tex>.png (whole texture), ui/<tex>_<k>.png (one sprite per rectangle), ui/index.json."""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import model_entities as me, wg2
from extract_minimaps import png, texture
from extract_designer_sprites import container
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/designer_sprites/ui')

def decode(arc, e):
    d = wg2.decompress(container(arc, e))[0]
    w, h = 1 << d[10], 1 << d[11]
    pal = [bytes((d[12 + 4 * i + 2], d[12 + 4 * i + 1], d[12 + 4 * i], d[12 + 4 * i + 3])) for i in range(256)]
    return w, h, [pal[p] for p in d[1036:1036 + w * h]]

def rects(d):
    return [list(struct.unpack_from('<4H', d, i)) for i in range(0, len(d) - 15, 16) if d[i + 12:i + 16] == b'\x80\x80\x80\x80']

def main():
    os.makedirs(OUT, exist_ok=True)
    A, C = me.Arc('DSN'), me.Arc('CHR')
    sets = [('chr34', C, 34, C, 35), ('dsn33', A, 33, A, 34), ('dsn48', A, 48, A, 49), ('dsn32', A, 32, A, 35), ('dsn31', A, 31, None, None)]
    idx = {}
    for name, ta, te, la, le in sets:
        w, h, px = decode(ta, te)
        open(os.path.join(OUT, name + '.png'), 'wb').write(png(w, h, b''.join(px)))
        ent = dict(texture=name + '.png', size=[w, h], source='%s %d' % ('CHR' if ta is C else 'DSN', te), sprites=[])
        if la:
            for k, (rx, ry, rw, rh) in enumerate(rects(wg2.decompress(container(la, le))[0])):
                if rw == 0 or rh == 0: continue
                f = '%s_%d.png' % (name, k)
                open(os.path.join(OUT, f), 'wb').write(png(rw, rh, b''.join(b''.join(px[(ry + y) * w + rx:(ry + y) * w + rx + rw]) for y in range(rh))))
                ent['sprites'].append(dict(k=k, file=f, rect=[rx, ry, rw, rh]))
            ent['rect_list'] = '%s %d' % ('CHR' if la is C else 'DSN', le)
        idx[name] = ent
    json.dump(idx, open(os.path.join(OUT, 'index.json'), 'w'), separators=(',', ':'))
    print({k: len(v['sprites']) for k, v in idx.items()})

if __name__ == '__main__':
    main()
