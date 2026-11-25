"""PNG writer for the exporters (standard library only).
png_from_rgba(w, h, rgba) -> PNG bytes. The game's textures are 8-bit palette images (at most 256 colours), so when the picture has 256 colours or fewer it is written as an indexed PNG
(PLTE + tRNS for the alpha, 1 / 2 / 4 / 8 bits per pixel, whichever fits): the same pixels as the RGBA file, about a quarter of its size. More than 256 colours: a plain RGBA PNG."""
import struct, zlib

def _chunk(t, b): return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)

def _rgba_png(w, h, rgba):
    raw = b''.join(b'\x00' + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    return b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + _chunk(b'IDAT', zlib.compress(raw, 9)) + _chunk(b'IEND', b'')

def png_from_rgba(w, h, rgba):
    cols = {}; idx = bytearray(w * h)
    for i in range(w * h):
        p = rgba[i * 4:i * 4 + 4]; k = cols.get(p)
        if k is None:
            k = cols[p] = len(cols)
            if k > 255: return _rgba_png(w, h, rgba)
        idx[i] = k
    n = len(cols); pal = sorted(cols, key=cols.get)
    bits = 1 if n <= 2 else 2 if n <= 4 else 4 if n <= 16 else 8; per = 8 // bits
    rows = []
    for y in range(h):
        r = idx[y * w:(y + 1) * w]
        if bits == 8: rows.append(b'\x00' + bytes(r))
        else:
            r = bytes(r) + b'\x00' * (-w % per); out = bytearray()
            for j in range(0, len(r), per):
                v = 0
                for q in range(per): v = (v << bits) | r[j + q]
                out.append(v)
            rows.append(b'\x00' + bytes(out))
    alpha = bytes(p[3] for p in pal).rstrip(b'\xff')      # tRNS only has to run up to the last entry that is not opaque
    png = b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, bits, 3, 0, 0, 0)) + _chunk(b'PLTE', b''.join(p[:3] for p in pal))
    if alpha: png += _chunk(b'tRNS', alpha)
    return png + _chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + _chunk(b'IEND', b'')
