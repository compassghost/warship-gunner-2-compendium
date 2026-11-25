"""Warship Gunner 2 archive access + the game's LZ decompressor (EE routine at 0x22E640 in SLUS_213.87)."""
import struct

def read_index(f):
    f.seek(0)
    n, base, unit, shift = struct.unpack('<4I', f.read(16))
    words = struct.unpack('<%dI' % (n + 1), f.read(4 * (n + 1)))
    mask = words[0]
    return [((w >> shift) * base, (w & mask) * unit) for w in words[1:]]

def decompress(src, pos=0):
    """Returns (output bytes, input bytes consumed). Token set, from the game's code:
       00            end
       1..1F         literal run of n bytes
       20..3F        literal run, n = ((c&0x1F)<<8)|next
       40..4F        fill: count=(c&0xF)+4, value=next byte
       50..5F        fill: count=(((c&0xF)<<8)|next)+4, value=next byte
       60..7F        continue copying n=(c&0x1F) more bytes from the previous back-reference
       80..FF        copy len=(c>>5) (4..7) bytes from dst-(((c&0x1F)<<8)|next)"""
    out = bytearray(); start = pos; n = len(src)
    c = src[pos]; pos += 1
    while c != 0:
        if c & 0x80:
            dist = ((c & 0x1F) << 8) | src[pos]; pos += 1
            ln = c >> 5
            s = len(out) - dist
            for _ in range(ln):
                out.append(out[s]); s += 1
            while True:
                c = src[pos]
                if (c & 0xE0) != 0x60: break
                pos += 1
                for _ in range(c & 0x1F):
                    out.append(out[s]); s += 1
        elif c & 0x40:
            if c & 0x10:
                ln = (((c & 0xF) << 8) | src[pos]) + 4; pos += 1
            else:
                ln = (c & 0xF) + 4
            out.extend(bytes([src[pos]]) * ln); pos += 1
            c = src[pos]
        else:
            if c & 0x20:
                ln = ((c & 0x1F) << 8) | src[pos]; pos += 1
            else:
                ln = c & 0x1F
            out.extend(src[pos:pos + ln]); pos += ln
            c = src[pos]
        pos += 1
    return bytes(out), pos - start


def decode_shtx(b):
    """Decode a decompressed 'SHTX' 8bpp image -> (width, height, RGBA bytes).
    Layout: 'SHTXFS' + 6 header bytes (b[10], b[11] = log2 width, log2 height), then a 256-entry RGBA palette
    (linear order; each entry is B,G,R,A), then width*height linear 8-bit indices.
    Alpha is a full 0..255 range."""
    assert b[:4] == b'SHTX'
    w, h = 1 << b[10], 1 << b[11]
    if len(b) != 12 + 1024 + w * h:
        raise ValueError('not an 8bpp SHTX image')
    pal = [b[12 + 4 * k:16 + 4 * k] for k in range(256)]
    # NOTE: the palette is already in linear order (it is a smooth ramp in file order); an earlier version wrongly
    # applied the PS2 CSM1 bit-3/4 swizzle, which mixed up colours and washed them out.
    pal = [p[2:3] + p[1:2] + p[0:1] + p[3:4] for p in pal]   # palette is stored B,G,R,A -> convert to R,G,B,A
    px = b[1036:1036 + w * h]
    return w, h, b''.join(pal[p] for p in px)
