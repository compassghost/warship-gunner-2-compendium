"""Find stores/loads to a given absolute address built as lui+imm: python tools/fnstore.py <addr hex> [lo hi]"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from fnlist import w
tgt = int(sys.argv[1], 16)
lo = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x100000
hi = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x2a0000
hiw = ((tgt + 0x8000) >> 16) & 0xffff
lo16 = tgt & 0xffff
for a in range(lo, hi, 4):
    v = w(a)
    if (v & 0xffff) == lo16 and (v >> 26) in (0x23, 0x2b, 0x21, 0x25, 0x29, 0x31, 0x39, 0x20, 0x24, 0x28):
        # look back 8 insns for lui with hiw into same base reg
        base = (v >> 21) & 31
        for b in range(a - 4, a - 40, -4):
            u = w(b)
            if (u >> 26) == 0xf and ((u >> 16) & 31) == base and (u & 0xffff) == hiw:
                print('%x: %08x (lui at %x)' % (a, v, b)); break
