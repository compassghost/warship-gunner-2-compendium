"""Disassemble the PS2 executable: python tools/mdis.py <start hex> <count words>  (MIPS64 LE, one word at a time; address = file offset + 0xff000)."""
import sys, struct
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS64, CS_MODE_LITTLE_ENDIAN
D = open(__import__('os').path.join(__import__('os').path.dirname(__file__), '../iso_extract/SLUS_213.87'), 'rb').read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 | CS_MODE_LITTLE_ENDIAN)
def dis(addr, n):
    out = []
    for i in range(n):
        a = addr + 4 * i; off = a - 0x100000 + 0x1000; w = D[off:off + 4]
        ins = list(md.disasm(w, a))
        out.append('%x: %s %s' % (a, ins[0].mnemonic, ins[0].op_str) if ins else '%x: .word %08x' % (a, struct.unpack('<I', w)[0]))
    return out
if __name__ == '__main__':
    print('\n'.join(dis(int(sys.argv[1], 16), int(sys.argv[2]))))
