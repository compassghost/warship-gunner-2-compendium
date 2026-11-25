"""Extract the design screen's part pictures ("blueprint" line art) from DSN.BIN into web/designer_sprites/.

Where they are (found 2026-11-17, see notes/designer_sprites.md): the design screen loader (0x198d40) reads DSN entries 36-40 (file ids 0x2b1d.. = 11000 + entry + 1).
Each is a CONTAINER of many small records, not a single image (wg2.decompress only decodes the FIRST stream, which is why they looked empty / sparse):
  DSN 36  907 LZ streams, each starting on a 16-byte boundary: one SHTXFS-like image per picture index (8bpp, w and h in the header, 2..256 colour palette; only 2 are used)
  DSN 38  raw u32 offsets of those streams (908 entries, last 0)
  DSN 37  raw (NOT compressed) 907 x 0x88-byte footprint records (the shape table the grid code reads at +4 + index * 0x88)
  DSN 39 / 40  145 more streams (a different image kind, 15-17 KB each) and their u32 offset table: not exported here.
Picture index = part record (DAT entry 7) u16[7..10] (plan view, per barrel count) and u16[13..16] (the other view, per barrel count).
Output: web/designer_sprites/p<index>.png (RGBA exactly as the stored palette: ink white, background transparent), web/designer_sprites/index.json."""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import model_entities as me, wg2
from extract_minimaps import png
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/designer_sprites')

def container(arc, e):
    o, s = arc.idx[e]; arc.f.seek(o); return arc.f.read(s)

def sprite(d):
    """Decoded stream -> (w, h, palette [RGBA], pixel indices)."""
    assert d[:6] == b'SHTXFS'
    w, h = struct.unpack_from('<HH', d, 6)
    n = (len(d) - 12 - w * h) // 4
    assert n >= 2 and 12 + 4 * n + w * h == len(d), 'unexpected layout'
    pal = [d[12 + 4 * i:16 + 4 * i] for i in range(n)]
    pal = [bytes((p[2], p[1], p[0], p[3])) for p in pal]            # stored B,G,R,A
    return w, h, pal, d[12 + 4 * n:]

def main():
    os.makedirs(OUT, exist_ok=True)
    A = me.Arc('DSN')
    raw36, raw37, raw38 = container(A, 36), container(A, 37), container(A, 38)
    offs = struct.unpack('<%dI' % (len(raw38) // 4), raw38)
    n = len(raw37) // 0x88
    pics = []
    for i in range(n):
        d, c = wg2.decompress(raw36, offs[i])
        w, h, pal, px = sprite(d)
        over = sum(1 for p in px if p >= len(pal))                      # a few sprites (40 of 907) use index 255 beyond a shorter palette: drawn with the last entry
        # index 255 beyond a shorter palette has no colour in the file and the game's blueprint shows no such marks: transparent (was drawn with the last entry, giving stray white bars)
        open(os.path.join(OUT, 'p%d.png' % i), 'wb').write(png(w, h, b''.join(pal[p] if p < len(pal) else b'\0\0\0\0' for p in px)))
        r = raw37[0x88 * i:0x88 * (i + 1)]
        fw, fh = r[0], r[1]
        cw_, ch_, cy_ = 4 * fw, 4 * fh, h - 4 * fh
        if cw_ > 0 and ch_ > 0 and cw_ <= w and cy_ >= 0:
            os.makedirs(os.path.join(OUT, 'crop'), exist_ok=True)
            cp = [pal[p] if p < len(pal) else b'\0\0\0\0' for p in px]
            open(os.path.join(OUT, 'crop', 'p%d.png' % i), 'wb').write(png(cw_, ch_, b''.join(b''.join(cp[(cy_ + y) * w:(cy_ + y) * w + cw_]) for y in range(ch_))))
        # texture is padded to (4*fw + pw) x (4*fh + ph), pw / ph in {0, 4, 8}; the padding is the RIGHT pw columns and the TOP ph rows, usually filled with palette index 0 (= white ink),
        # which is the "solid bar" seen on some pictures. Visible art = crop [0, ph, 4*fw, 4*fh] (x, y, w, h). Confirmed by exact size match: 390 pictures no padding, 212 right 4 cols solid,
        # 121 top 4 rows solid, 57 both; the game blits a 4*fw x 4*fh sprite.
        pw, ph = w - 4 * raw37[0x88 * i], h - 4 * raw37[0x88 * i + 1]
        pics.append(dict(i=i, file='p%d.png' % i, w=w, h=h, crop=[0, ph, 4 * raw37[0x88 * i], 4 * raw37[0x88 * i + 1]], pal0=pal[0].hex(), pal1=pal[1].hex(), over255=over,
                         fw=fw, fh=fh, margins=list(r[4:8]), rows=['%08x' % struct.unpack_from('<I', r, 8 + 4 * k)[0] for k in range(min(fh, 32))]))
    json.dump(dict(count=n, source='DSN 36 (pictures) / 38 (stream offsets) / 37 (0x88 footprint records)', pictures=pics), open(os.path.join(OUT, 'index.json'), 'w'), separators=(',', ':'))
    print(n, 'pictures written to', OUT)
    hulls(A)

def rle(row):
    out = []; i = 0
    while i < len(row):
        j = i
        while j < len(row) and row[j] == row[i]: j += 1
        if row[i]: out.append([row[i], i, j - i])                      # [value, first column, run length]
        i = j
    return out

def hulls(A):
    """DSN 39 = 145 hull records (hull order = project hull table, designer.json hulls 200..344), offsets in DSN 40.
    Each decoded stream = a 160 x 85 byte cell grid (13,600 bytes: hull side view rows 22-32, plan view rows 51-66, one byte per design-grid cell, value = bit flags of the
    hull section) followed by a second, nested LZ stream (starts with token 0x0c + 'SHTXFS') = the 640 x 340 blueprint picture (8bpp, 256-entry palette)."""
    raw39, raw40 = container(A, 39), container(A, 40)
    offs = struct.unpack('<%dI' % (len(raw40) // 4), raw40)
    hs = []
    for k in range(len(offs) - 1):
        d, c = wg2.decompress(raw39, offs[k])
        i = d.find(b'\x0cSHTXFS'); assert i == 13600, (k, i)
        img, c2 = wg2.decompress(d, i); assert i + c2 == len(d)
        w, h = struct.unpack_from('<HH', img, 6)
        pal = [bytes((img[12 + 4 * j + 2], img[12 + 4 * j + 1], img[12 + 4 * j], img[12 + 4 * j + 3])) for j in range(256)]
        px = img[1036:]; rows = len(px) // w
        open(os.path.join(OUT, 'hull%d.png' % k), 'wb').write(png(w, rows, b''.join(pal[p] for p in px)))
        g = d[:13600]
        hs.append(dict(i=k, file='hull%d.png' % k, w=w, h=rows, header_h=h, grid=[rle(g[y * 160:(y + 1) * 160]) for y in range(85)]))
    json.dump(dict(count=len(hs), source='DSN 39 / 40', grid_cols=160, grid_rows=85, hulls=hs), open(os.path.join(OUT, 'hulls.json'), 'w'), separators=(',', ':'))
    print(len(hs), 'hull blueprints + grids written')

if __name__ == '__main__':
    main()

