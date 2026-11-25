"""Scan functions in a range for loads of given struct offsets: python tools/fnscan.py <start> <end> <off,off,..>"""
import sys, struct
sys.path.insert(0, __import__('os').path.dirname(__file__))
from fnlist import funcs, w
a0, a1 = int(sys.argv[1], 16), int(sys.argv[2], 16)
offs = [int(x, 0) for x in sys.argv[3].split(',')]
fs = funcs(a0, a1)
for i, a in enumerate(fs):
    e = fs[i + 1] if i + 1 < len(fs) else a1
    hits = {}
    fl = 0
    for x in range(a, e, 4):
        v = w(x); op = v >> 26; imm = v & 0xffff
        if op in (0x25, 0x24, 0x21, 0x20, 0x23) and imm in offs:  # lhu lbu lh lb lw
            hits[imm] = hits.get(imm, 0) + 1
        if v >> 21 == 0x230 and (v & 0x3f) in (0x20,):  # cop1 W fmt cvt.s.w
            fl += 1
    if hits and (len(hits) >= 1):
        print('%x size %d hits %s cvt %d' % (a, e - a, hits, fl))
