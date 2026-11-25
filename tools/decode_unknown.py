"""Decoders for archive entry kinds that are not plain single LZ streams (see notes/archive_formats.md).

BUNDLES: an archive entry may hold many LZ streams back to back. A separate entry holds a u32 offset table (stored
uncompressed; wg2.decompress sees a leading 0 byte and returns b'' - that is why DSN 38 and 40 looked "empty").
  DSN 38 = offset table (908 u32, last 0) of the stream bundle DSN 36: 907 SHTXFS sprites (the design-screen part pictures?)
  DSN 40 = offset table (146 u32) of the bundle DSN 39: 145 streams of ~16 KB (see notes)
Run: python tools/decode_unknown.py sheet36 out.png   -> contact sheet of DSN 36 sprites
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
import wg2
ROOT = os.path.join(os.path.dirname(__file__), '..')

class Arc:
    def __init__(self, name):
        self.f = open(os.path.join(ROOT, 'iso_extract', name + '.BIN'), 'rb'); self.idx = wg2.read_index(self.f)
    def raw(self, i):
        o, s = self.idx[i]; self.f.seek(o); return self.f.read(s)

def offsets(tab):
    n = len(tab) // 4
    offs = list(struct.unpack('<%dI' % n, tab[:n * 4]))
    while offs and offs[-1] == 0 and len(offs) > 1: offs.pop()
    return offs

def bundle(arc, table_entry, data_entry):
    """-> list of decompressed streams of the bundle."""
    raw = arc.raw(data_entry); out = []
    for o in offsets(arc.raw(table_entry)):
        if o >= len(raw): continue      # DSN 40's last word is the end-of-bundle sentinel
        out.append(wg2.decompress(raw[o:])[0])
    return out

def shtx_image(d):
    """SHTXFS with explicit size: u16 w, h at offset 6, palette (BGRA) at 12, 8bpp pixels. Returns PIL RGBA image."""
    from PIL import Image
    if d[:6] != b'SHTXFS': return None
    w, h = struct.unpack_from('<HH', d, 6)
    # palette size is variable: entries = (len - 12 - w*h) / 4 (128..256 seen in DSN 36); pixels start at 12 + 4*entries
    ne = (len(d) - 12 - w * h) // 4
    if ne < 1 or ne > 256:       # hull pictures (DSN 39): full 256-entry palette and fewer rows than the header height (340 of 344)
        ne = 256; h = (len(d) - 1036) // w
        if h <= 0: return None
    pal = d[12:12 + 4 * ne]; px = d[12 + 4 * ne:12 + 4 * ne + w * h]
    P = [(pal[4*i+2], pal[4*i+1], pal[4*i], pal[4*i+3]) for i in range(ne)] + [(0, 0, 0, 0)] * (256 - ne)
    # 40 sprites use index 255 (one row / column of w pixels) beyond their truncated palette: drawn transparent here, meaning unknown
    im = Image.new('RGBA', (w, h)); im.putdata([P[p] for p in px]); return im

def sheet(images, cols=30, cell=None, bg=(40, 40, 60, 255)):
    from PIL import Image
    cw = max(i.width for i in images) + 2; ch = max(i.height for i in images) + 2
    rows = (len(images) + cols - 1) // cols
    S = Image.new('RGBA', (cols * cw, rows * ch), bg)
    for k, im in enumerate(images): S.paste(im, ((k % cols) * cw, (k // cols) * ch), im)
    return S

def export36(outdir):
    """Write every DSN 36 sprite as sprite_NNN.png plus sprites.json [{i, w, h}] (index = shape index of part record u16[7..10])."""
    import json
    os.makedirs(outdir, exist_ok=True); meta = []
    for k, d in enumerate(bundle(Arc('DSN'), 38, 36)):
        im = shtx_image(d); im.save(os.path.join(outdir, 'sprite_%03d.png' % k)); meta.append(dict(i=k, w=im.width, h=im.height, hdr_h=struct.unpack_from('<H', d, 8)[0]))
    json.dump(meta, open(os.path.join(outdir, 'sprites.json'), 'w')); return len(meta)

MASK_W, MASK_H = 160, 85

def hull_item(d):
    """One DSN 39 item (decompressed): 160 x 85 raw bytes = zone masks of the hull (side view above plan view, one cell = 4 px of the
    picture), then a second LZ stream = SHTXFS hull blueprint picture 640 x 344 (340 rows stored). Returns (mask bytes, PIL image)."""
    m = d[:MASK_W * MASK_H]; pic = wg2.decompress(d[MASK_W * MASK_H:])[0]
    return m, shtx_image(pic)

def export39(outdir):
    """hull_NNN.png (blueprint picture), hull_NNN_mask.png (zone mask coloured by bit), hulls.json."""
    import json
    from PIL import Image
    os.makedirs(outdir, exist_ok=True); cols = {0: (0, 0, 0), 1: (255, 0, 0), 2: (255, 160, 0), 4: (255, 255, 0), 8: (0, 255, 0), 16: (0, 200, 255), 32: (120, 120, 255)}
    n = 0
    # hull id of item k: DAT entry 8 = hull table, 40-byte records, u16[0] = hull id, u16[17] = DSN 39 item index (= record number for 0..144)
    import model_entities as me
    dat8 = me.Arc('DAT').get(8); hid = {}
    for r in range(150):
        h, idx = struct.unpack_from('<H', dat8, 40 * r)[0], struct.unpack_from('<H', dat8, 40 * r + 34)[0]
        if r < 145: hid[r] = h
    json.dump(hid, open(os.path.join(outdir, 'hulls.json'), 'w'))
    for k, d in enumerate(bundle(Arc('DSN'), 40, 39)):
        m, im = hull_item(d); im.save(os.path.join(outdir, 'hull_%03d.png' % k))
        mi = Image.new('RGB', (MASK_W, MASK_H)); mi.putdata([cols.get(x, (255, 0, 255)) for x in m]); mi.save(os.path.join(outdir, 'hull_%03d_mask.png' % k))
        open(os.path.join(outdir, 'hull_%03d_mask.bin' % k), 'wb').write(m); n += 1
    return n

def streams(raw, step=16):
    """Walk a multi-stream entry without an offset table: LZ stream, zero padding to the next 16-byte boundary, next stream.
    Returns [(offset, decompressed)]."""
    out = []; pos = 0
    while pos < len(raw) and any(raw[pos:pos + 64]):
        try: d, u = wg2.decompress(raw[pos:])
        except Exception: break
        out.append((pos, d)); pos += u      # the next stream starts right after the 00 end token (verified on MAP 2 / 13, DSN 17, CHR 15)
    return out

if __name__ == '__main__':
    a = Arc('DSN')
    if sys.argv[1] == 'export39':
        print(export39(sys.argv[2]), 'hulls written')
    if sys.argv[1] == 'export36':
        print(export36(sys.argv[2]), 'sprites written')
    if sys.argv[1] == 'sheet36':
        ims = [shtx_image(d) for d in bundle(a, 38, 36)]
        ims = [i for i in ims if i]
        print(len(ims), 'images; sizes', sorted(set((i.width, i.height) for i in ims))[:20])
        sheet(ims, cols=int(sys.argv[3]) if len(sys.argv) > 3 else 20).save(sys.argv[2])
