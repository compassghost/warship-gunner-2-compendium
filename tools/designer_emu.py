"""Run the game's own design-screen code (SLUS_213.87) on design records from DAT entry 26, with the real DAT tables, using tools/mips_emu.py.
  python tools/designer_emu.py [design index]
Memory map used here: part table (DAT 7) etc. are placed at fixed addresses and the gp-relative pointers the game sets at 0x103f10.. are filled in.
gp = 0x2b64f0.  gp-0x7df0 part table (0x90 rows), -0x7dec hull table (0x28 rows, DAT 8), -0x7de8 = DAT8 + 0x16a8, -0x7de4 DAT 9 (0x44 rows),
-0x7de0 DAT 10 (u16 curve), counts at -0x7dcc / -0x7dca (u16) and -0x7dc8 (u16)."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
import wg2
import mips_emu as E
ROOT = os.path.join(os.path.dirname(__file__), '..')
GP = 0x2b64f0

def dat(i):
    f = open(os.path.join(ROOT, 'iso_extract/DAT.BIN'), 'rb'); idx = wg2.read_index(f); o, s = idx[i]; f.seek(o)
    return wg2.decompress(f.read(s))[0]

def make_cpu():
    c = E.CPU(); c.r[28] = GP
    def memcpy(cpu): cpu.put(cpu.r[4], cpu.get(cpu.r[5], cpu.r[6])); cpu.r[2] = cpu.r[4]
    c.hooks[0x27f874] = memcpy
    def strcpy(cpu):
        d, s = cpu.r[4], cpu.r[5]; n = 0
        while True:
            b = cpu.rd(s + n, 1); cpu.wr(d + n, 1, b); n += 1
            if b == 0 or n > 64: break
        cpu.r[2] = d
    c.hooks[0x2803a0] = strcpy
    def memset(cpu): cpu.put(cpu.r[4], bytes([cpu.r[5] & 255]) * cpu.r[6]); cpu.r[2] = cpu.r[4]
    c.hooks[0x27f924] = memset
    a = 0x1000000; D = {}
    for i in (7, 8, 9, 10):
        b = dat(i); c.put(a, b); D[i] = (a, len(b)); a += (len(b) + 0xfff) & ~0xfff
    a7, n7 = D[7]; a8, n8 = D[8]; a9, n9 = D[9]; a10, _ = D[10]
    # base-part count: records until byte4 == 5 (0x198cf8)
    cnt = 0
    while cnt < n7 // 0x90 and c.rd(a7 + cnt * 0x90 + 4, 1) != 5: cnt += 1
    W = lambda off, n, v: c.wr(GP + off, n, v)
    W(-0x7df0, 4, a7); W(-0x7dec, 4, a8); W(-0x7de8, 4, a8 + 0x16a8); W(-0x7de4, 4, a9); W(-0x7de0, 4, a10)
    W(-0x7dcc, 2, cnt); W(-0x7dca, 2, n7 // 0x90 - cnt); W(-0x7dc8, 2, n9 // 0x44)
    c.tab = dict(part=a7, hull=a8, sys=a9, curve=a10, nparts=cnt)
    return c

def designs():
    b = dat(26)
    return [b[2048 * i:2048 * (i + 1)] for i in range(len(b) // 2048)]

if __name__ == '__main__':
    c = make_cpu(); ds = designs(); print(len(ds), 'designs', c.tab)
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    DSG, ST = 0x1200000, 0x1210000
    c.put(DSG, ds[k]); c.put(ST, b'\0' * 0x100)
    c.run(0x19bbe8, (ST, DSG), max_steps=5000000)
    print(c.get(ST, 0x60).hex())
