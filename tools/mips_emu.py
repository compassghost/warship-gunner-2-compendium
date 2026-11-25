"""Tiny MIPS / R5900 interpreter, just enough to run small pure-computation routines of SLUS_213.87 on the game's own data.
Used by tools/decode_weather.py to evaluate the weather / time-of-day blender (0x148b78) exactly as the game does,
instead of re-implementing it by hand.  Not a full emulator: no syscalls, no 128-bit ops, no TLB, no cop0/vu.
Memory is one flat 64 MB bytearray; the executable is loaded at (file offset + 0xff000) like the game does.
Hooks (python callables keyed by address) replace library calls such as memcpy (0x27f874).
"""
import struct, os

EXE = os.path.join(os.path.dirname(__file__), '..', 'iso_extract', 'SLUS_213.87')
LOAD = 0xff000
MASK = 0xFFFFFFFF


def s32(x): x &= MASK; return x - (1 << 32) if x & 0x80000000 else x
def s16(x): x &= 0xFFFF; return x - 0x10000 if x & 0x8000 else x
def s8(x): x &= 0xFF; return x - 0x100 if x & 0x80 else x
def f2i(f): return struct.unpack('<I', struct.pack('<f', f))[0]
def i2f(i): return struct.unpack('<f', struct.pack('<I', i & MASK))[0]


class CPU:
    def __init__(self, size=0x4000000):
        self.m = bytearray(size)
        d = open(EXE, 'rb').read()
        self.m[LOAD:LOAD + len(d)] = d
        self.r = [0] * 32          # store as unsigned 32-bit (enough for this code: addresses and ints)
        self.f = [0] * 32          # float registers as raw 32-bit ints
        self.hi = self.lo = self.hi1 = self.lo1 = 0
        self.fcc = False
        self.hooks = {}
        self.pc = 0

    # ---- memory (0x7000xxxx scratchpad RAM is mapped to 0x3f80000; 0x2xxxxxxx / 0x3xxxxxxx uncached mirrors to RAM)
    @staticmethod
    def tr(a):
        a &= MASK
        if (a >> 28) == 7: return 0x3f80000 + (a & 0x3fff)
        if 0x20000000 <= a < 0x40000000: return a & 0x1ffffff
        return a
    def rd(self, a, n): a = self.tr(a); return int.from_bytes(self.m[a:a + n], 'little')
    def wr(self, a, n, v): a = self.tr(a); self.m[a:a + n] = (v & ((1 << (8 * n)) - 1)).to_bytes(n, 'little')
    def put(self, a, data): a = self.tr(a); self.m[a:a + len(data)] = data
    def get(self, a, n): a = self.tr(a); return bytes(self.m[a:a + n])

    def setr(self, n, v):
        if n: self.r[n] = v & MASK

    def run(self, addr, args=(), sp=0x3f00000, max_steps=2000000):
        """Call the function at addr (jal semantics) until it returns to a sentinel address. Returns v0."""
        for i, a in enumerate(args): self.r[4 + i] = a & MASK
        self.r[29] = sp
        SENT = 0x00000FF0
        self.r[31] = SENT
        self.pc = addr
        steps = 0
        while self.pc != SENT:
            steps += 1
            if steps > max_steps: raise RuntimeError('step limit')
            if self.pc in self.hooks:
                self.hooks[self.pc](self)
                self.pc = self.r[31]
                continue
            self.step()
        return self.r[2]

    def step(self):
        pc = self.pc
        w = self.rd(pc, 4)
        self.exec_one(w, pc)

    def delay(self, pc_next_after_delay_target):
        pass

    def exec_one(self, w, pc):
        # normal instruction; branches handled with explicit delay slot execution
        r = self.r
        op = w >> 26
        rs = (w >> 21) & 31; rt = (w >> 16) & 31; rd = (w >> 11) & 31; sa = (w >> 6) & 31; fn = w & 63
        imm = w & 0xFFFF; simm = s16(imm)
        nxt = pc + 4

        def branch(cond, likely=False):
            tgt = pc + 4 + (simm << 2)
            if cond:
                self.exec_delay(pc + 4)
                self.pc = tgt & MASK
            else:
                if likely: self.pc = pc + 8
                else:
                    self.exec_delay(pc + 4); self.pc = pc + 8

        if op == 0:
            if fn == 0: self.setr(rd, r[rt] << sa)
            elif fn == 2: self.setr(rd, r[rt] >> sa)
            elif fn == 3: self.setr(rd, s32(r[rt]) >> sa)
            elif fn == 4: self.setr(rd, r[rt] << (r[rs] & 31))
            elif fn == 6: self.setr(rd, r[rt] >> (r[rs] & 31))
            elif fn == 7: self.setr(rd, s32(r[rt]) >> (r[rs] & 31))
            elif fn == 8:   # jr
                t = r[rs]; self.exec_delay(pc + 4); self.pc = t; return
            elif fn == 9:   # jalr
                t = r[rs]; self.setr(rd, pc + 8); self.exec_delay(pc + 4); self.pc = t; return
            elif fn == 10:  # movz
                if r[rt] == 0: self.setr(rd, r[rs])
            elif fn == 11:  # movn
                if r[rt] != 0: self.setr(rd, r[rs])
            elif fn == 13: pass  # break
            elif fn == 16: self.setr(rd, self.hi)
            elif fn == 18: self.setr(rd, self.lo)
            elif fn == 24:  # mult (R5900: optional rd gets lo)
                p = s32(r[rs]) * s32(r[rt]); self.lo = s32(p) & MASK; self.hi = s32(p >> 32) & MASK
                if rd: self.setr(rd, self.lo)
            elif fn == 25:
                p = r[rs] * r[rt]; self.lo = s32(p) & MASK; self.hi = s32(p >> 32) & MASK
                if rd: self.setr(rd, self.lo)
            elif fn == 26:  # div
                a, b = s32(r[rs]), s32(r[rt])
                if b == 0: self.lo = self.hi = 0
                else:
                    q = abs(a) // abs(b); q = q if (a < 0) == (b < 0) else -q
                    self.lo = q & MASK; self.hi = (a - q * b) & MASK
            elif fn == 27:
                a, b = r[rs], r[rt]
                if b == 0: self.lo = self.hi = 0
                else: self.lo = (a // b) & MASK; self.hi = (a % b) & MASK
            elif fn in (32, 33): self.setr(rd, r[rs] + r[rt])
            elif fn in (34, 35): self.setr(rd, r[rs] - r[rt])
            elif fn == 36: self.setr(rd, r[rs] & r[rt])
            elif fn == 37: self.setr(rd, r[rs] | r[rt])
            elif fn == 38: self.setr(rd, r[rs] ^ r[rt])
            elif fn == 39: self.setr(rd, ~(r[rs] | r[rt]))
            elif fn == 42: self.setr(rd, 1 if s32(r[rs]) < s32(r[rt]) else 0)
            elif fn == 43: self.setr(rd, 1 if r[rs] < r[rt] else 0)
            elif fn == 45: self.setr(rd, r[rs] | r[rt])      # daddu with zero-extended 32-bit values (move)
            else: raise NotImplementedError('special %x at %x' % (fn, pc))
        elif op == 1:
            if rt == 0: branch(s32(r[rs]) < 0)
            elif rt == 1: branch(s32(r[rs]) >= 0)
            elif rt == 2: branch(s32(r[rs]) < 0, True)
            elif rt == 3: branch(s32(r[rs]) >= 0, True)
            else: raise NotImplementedError('regimm %d at %x' % (rt, pc))
            return
        elif op == 2:
            self.exec_delay(pc + 4); self.pc = ((pc + 4) & 0xF0000000) | ((w & 0x3FFFFFF) << 2); return
        elif op == 3:
            self.setr(31, pc + 8); tgt = ((pc + 4) & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
            self.exec_delay(pc + 4); self.pc = tgt; return
        elif op == 4: branch(r[rs] == r[rt]); return
        elif op == 5: branch(r[rs] != r[rt]); return
        elif op == 6: branch(s32(r[rs]) <= 0); return
        elif op == 7: branch(s32(r[rs]) > 0); return
        elif op in (8, 9): self.setr(rt, r[rs] + simm)
        elif op == 10: self.setr(rt, 1 if s32(r[rs]) < simm else 0)
        elif op == 11: self.setr(rt, 1 if r[rs] < (simm & MASK) else 0)
        elif op == 12: self.setr(rt, r[rs] & imm)
        elif op == 13: self.setr(rt, r[rs] | imm)
        elif op == 14: self.setr(rt, r[rs] ^ imm)
        elif op == 15: self.setr(rt, imm << 16)
        elif op == 17:  # COP1
            if rs == 0: self.setr(rt, self.f[rd])
            elif rs == 4: self.f[rd] = r[rt]
            elif rs == 2: self.setr(rt, 0)  # cfc1
            elif rs == 6: pass
            elif rs == 8:   # bc1
                nd = (rt >> 1) & 1; tf = rt & 1
                cond = (self.fcc == bool(tf))
                if cond:
                    self.exec_delay(pc + 4); self.pc = (pc + 4 + (simm << 2)) & MASK
                else:
                    if nd: self.pc = pc + 8
                    else: self.exec_delay(pc + 4); self.pc = pc + 8
                return
            elif rs == 16:  # S
                a, b = i2f(self.f[rd]), i2f(self.f[rt])   # fs = rd, ft = rt; fd = sa
                fd = sa; fs = rd; ft = rt
                a, b = i2f(self.f[fs]), i2f(self.f[ft])
                def put(v): self.f[fd] = f2i(v)
                if fn == 0: put(a + b)
                elif fn == 1: put(a - b)
                elif fn == 2: put(a * b)
                elif fn == 3: put(a / b if b else float('inf'))
                elif fn == 4: put(a ** 0.5)
                elif fn == 5: put(abs(a))
                elif fn == 6: self.f[fd] = self.f[fs]
                elif fn == 7: put(-a)
                elif fn == 13 or fn == 36:  # trunc.w.s / cvt.w.s
                    import math
                    self.f[fd] = int(math.trunc(a)) & MASK if fn == 13 else int(round(a) if False else math.trunc(a)) & MASK
                elif fn == 0x16: put(a / (b ** 0.5) if b > 0 else 0.0)                     # rsqrt.s (R5900)
                elif fn == 0x18: self.acc = a + b                                          # adda.s
                elif fn == 0x19: self.acc = a - b                                          # suba.s
                elif fn == 0x1a: self.acc = a * b                                          # mula.s
                elif fn == 0x1c: put(getattr(self, 'acc', 0.0) + a * b)                    # madd.s
                elif fn == 0x1d: put(getattr(self, 'acc', 0.0) - a * b)                    # msub.s
                elif fn == 0x1e: self.acc = getattr(self, 'acc', 0.0) + a * b              # madda.s
                elif fn == 0x1f: self.acc = getattr(self, 'acc', 0.0) - a * b              # msuba.s
                elif fn == 0x28: put(max(a, b))
                elif fn == 0x29: put(min(a, b))
                elif fn == 50: self.fcc = (a == b)
                elif fn == 52: self.fcc = (a < b)   # c.olt
                elif fn == 54: self.fcc = (a <= b)  # c.ole
                elif fn == 60: self.fcc = (a < b)   # c.lt
                elif fn == 62: self.fcc = (a <= b)  # c.le
                elif fn == 48 or fn == 49 or fn == 51 or fn == 53 or fn == 55: self.fcc = False
                else: raise NotImplementedError('cop1.s %d at %x' % (fn, pc))
            elif rs == 20:  # W
                fd = sa; fs = rd
                if fn == 32: self.f[fd] = f2i(float(s32(self.f[fs])))   # cvt.s.w
                else: raise NotImplementedError('cop1.w %d at %x' % (fn, pc))
            else: raise NotImplementedError('cop1 rs %d at %x' % (rs, pc))
        elif op == 20: branch(r[rs] == r[rt], True); return
        elif op == 21: branch(r[rs] != r[rt], True); return
        elif op == 22: branch(s32(r[rs]) <= 0, True); return
        elif op == 23: branch(s32(r[rs]) > 0, True); return
        elif op == 30:  # lq (low 32 bits only)
            self.setr(rt, self.rd((r[rs] + simm) & ~15, 4))
        elif op == 31:  # sq
            self.put((r[rs] + simm) & ~15 & MASK, struct.pack('<I', r[rt]) + b'\0' * 12)
        elif op == 28:  # MMI (R5900)
            if fn == 0x00:    # madd: (hi:lo) += rs*rt, rd = lo
                acc = (s32(self.hi) << 32) | self.lo
                acc += s32(r[rs]) * s32(r[rt])
                self.lo = acc & MASK; self.hi = (acc >> 32) & MASK
                if rd: self.setr(rd, self.lo)
            elif fn == 0x18: p = s32(r[rs]) * s32(r[rt]); self.lo1 = s32(p) & MASK; self.hi1 = s32(p >> 32) & MASK; (rd and self.setr(rd, self.lo1))
            elif fn == 0x19: p = r[rs] * r[rt]; self.lo1 = s32(p) & MASK; self.hi1 = s32(p >> 32) & MASK; (rd and self.setr(rd, self.lo1))
            elif fn == 0x1a:
                a, b = s32(r[rs]), s32(r[rt])
                if b == 0: self.lo1 = self.hi1 = 0
                else:
                    q = abs(a) // abs(b); q = q if (a < 0) == (b < 0) else -q
                    self.lo1 = q & MASK; self.hi1 = (a - q * b) & MASK
            elif fn == 0x12: self.setr(rd, self.lo1)
            elif fn == 0x10: self.setr(rd, self.hi1)
            elif fn == 0x20:  # madd1
                acc = (s32(self.hi1) << 32) | self.lo1
                acc += s32(r[rs]) * s32(r[rt])
                self.lo1 = acc & MASK; self.hi1 = (acc >> 32) & MASK
                if rd: self.setr(rd, self.lo1)
            elif fn == 0x20 or fn == 0x24 or fn == 0x28:  # madd family not expected
                raise NotImplementedError('mmi madd at %x' % pc)
            else:
                if fn == 0x1f or fn == 0:  # clz-like encodings seen only in data
                    raise NotImplementedError('mmi %x at %x' % (fn, pc))
                raise NotImplementedError('mmi %x at %x' % (fn, pc))
        elif op == 26: pass   # ldl: handled together with ldr (8-byte unaligned copy idiom)
        elif op == 27:        # ldr: load 8 bytes at addr; low word -> reg, high word kept in a shadow (only used for sdl/sdr copies)
            a = r[rs] + simm; self.setr(rt, self.rd(a, 4)); self.hi_sh = getattr(self, 'hi_sh', {}); self.hi_sh[rt] = self.rd(a + 4, 4)
        elif op == 44: pass   # sdl
        elif op == 45:        # sdr
            a = r[rs] + simm; self.wr(a, 4, r[rt]); self.wr(a + 4, 4, getattr(self, 'hi_sh', {}).get(rt, 0))
        elif op == 34:        # lwl (little endian): the bytes addr-n+1..addr become the top n bytes of the register
            a = r[rs] + simm; n = (a & 3) + 1; sh = (4 - n) * 8; self.setr(rt, (r[rt] & ((1 << sh) - 1)) | (self.rd(a - n + 1, n) << sh))
        elif op == 38:        # lwr: the bytes addr..end of the aligned word become the low n bytes of the register
            a = r[rs] + simm; n = 4 - (a & 3); old = r[rt]; self.setr(rt, (old & ~((1 << (8 * n)) - 1) & 0xffffffff) | self.rd(a, n))
        elif op == 42:        # swl: the top n bytes of the register go to addr-n+1..addr
            a = r[rs] + simm; n = (a & 3) + 1; self.wr(a - n + 1, n, (r[rt] & 0xffffffff) >> ((4 - n) * 8))
        elif op == 46:        # swr: the low n bytes of the register go to addr..end of the aligned word
            a = r[rs] + simm; n = 4 - (a & 3); self.wr(a, n, r[rt] & ((1 << (8 * n)) - 1))
        elif op == 32: self.setr(rt, s8(self.rd(r[rs] + simm, 1)))
        elif op == 33: self.setr(rt, s16(self.rd(r[rs] + simm, 2)))
        elif op == 35: self.setr(rt, self.rd(r[rs] + simm, 4))
        elif op == 36: self.setr(rt, self.rd(r[rs] + simm, 1))
        elif op == 37: self.setr(rt, self.rd(r[rs] + simm, 2))
        elif op == 40: self.wr(r[rs] + simm, 1, r[rt])
        elif op == 41: self.wr(r[rs] + simm, 2, r[rt])
        elif op == 43: self.wr(r[rs] + simm, 4, r[rt])
        elif op == 49: self.f[rt] = self.rd(r[rs] + simm, 4)
        elif op == 57: self.wr(r[rs] + simm, 4, self.f[rt])
        elif op == 63: self.wr(r[rs] + simm, 8, r[rt])       # sd (low 32 bits only)
        elif op == 55: self.setr(rt, self.rd(r[rs] + simm, 4))  # ld (low 32 bits only)
        else: raise NotImplementedError('op %d at %x' % (op, pc))
        self.pc = nxt

    def exec_delay(self, pc):
        """Execute the delay-slot instruction at pc (must not be a branch)."""
        save = self.pc
        w = self.rd(pc, 4)
        self.exec_one(w, pc)
        self.pc = save
