"""Find `addiu rX, $zero, N ; ... sb rX, 0x10(rY)` patterns (mount state byte writes) in a range: python tools/fnstate.py <lo> <hi>"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from fnlist import w, funcs
lo, hi = int(sys.argv[1], 16), int(sys.argv[2], 16)
fs = funcs(lo, hi)
for a in range(lo, hi, 4):
    v = w(a)
    if (v >> 26) == 0x28 and (v & 0xffff) == 0x10:       # sb rt, 0x10(rs)
        rt = (v >> 16) & 31; val = None
        for b in range(a - 4, a - 32, -4):
            u = w(b)
            if (u >> 26) == 9 and ((u >> 16) & 31) == rt and ((u >> 21) & 31) == 0: val = u & 0xffff; break
            if (u >> 16) & 31 == rt and (u >> 26) not in (0x2b, 0x28, 0x29, 4, 5): break
        if rt == 0: val = 0
        f = max([x for x in fs if x <= a] or [0])
        print('%x in %x: sb r%d (=%s), 0x10(r%d)' % (a, f, rt, val, (v >> 21) & 31))
