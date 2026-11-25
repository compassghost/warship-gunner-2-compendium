"""List function starts (addiu sp,sp,-N prologue) in a range of SLUS_213.87 with size and callees: python tools/fnlist.py <start hex> <end hex>"""
import sys, struct, os
D = open(os.path.join(os.path.dirname(__file__), '../iso_extract/SLUS_213.87'), 'rb').read()
def w(a): o = a - 0xff000; return struct.unpack('<I', D[o:o + 4])[0]
def funcs(a0, a1):
    st = []
    for a in range(a0, a1, 4):
        x = w(a)
        if (x >> 16) == 0x27bd and (x & 0x8000):  # addiu sp,sp,-N
            st.append(a)
    return st
if __name__ == '__main__':
    a0, a1 = int(sys.argv[1], 16), int(sys.argv[2], 16)
    fs = funcs(a0, a1)
    for i, a in enumerate(fs):
        e = fs[i + 1] if i + 1 < len(fs) else a1
        calls = sorted({(w(x) & 0x3ffffff) << 2 for x in range(a, e, 4) if (w(x) >> 26) == 3})
        print('%x size %d calls %s' % (a, e - a, ' '.join('%x' % c for c in calls)))
