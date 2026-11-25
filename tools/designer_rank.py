"""Evaluation ranks of the design screen / S-rank medal (SLUS_213.87 0x1f4f80: offensive 0x1f5a58, anti-air 0x1f5b10, armor 0x1f5cd8, response 0x1f5e68, command 0x1f6098,
mobility 0x1f6100, overall 0x1f61d0), decoded from the code and checked against the game's own functions (run in tools/designer_emu.py) for all 530 stock designs.
  python tools/designer_rank.py            -> self-check (python port vs the executable run in the emulator)
  python tools/designer_rank.py table      -> every design's six scores

Each category gives a score of 1, 4, 6, 8 or 10 (10 is the top grade, shown as A); the overall rank is the SUM of the six: >= 60 index 0 (S: all six at 10),
>= 50 index 1, >= 30 index 2, >= 10 index 3, else 4. A design is rated per category as follows (design mounts: part id u32, slot category b8 = byte 0xa, barrels-1 = byte 0xb;
part row = DAT 7 record, u16 numbering as in designer_vp.Tables):

OFFENSIVE   the 7 weapon slot categories (b8 0..6) each keep ONE representative part: the part with the LOWEST row index in the table among the mounts of that category, with the
            barrel factor f of the mount that first brought it (f = barrels for 1..5 barrels, 7 for 6 or more; 0x1f4cd0). value = part.u16[32] * f, only parts whose kind
            (byte 6) is not 3. The best value over the categories decides: >= 10000 -> 10, >= 1000 -> 8, >= 500 -> 6, >= 250 -> 4, else 1.
            (A single big weapon counts, weapons are not added up: 1 Magnetic Pulse Cannon (u16[32] = 15000) or Gun (10000) gives 10.)
ARMOR       the same best value but over parts whose kind is not 6 / 7, turned into a "gun class" 1..15 by the thresholds 7 9 11 19 37 49 102 124 151 181 215 295 395 512
            (class 1 below 7, 2 from 7, 3 from 9, 4 from 11, 5 from 19, 6 from 37, 7 from 49, 8 from 102, 9 from 124, 10 from 151, 11 from 181, 12 from 215, 13 from 295,
            14 from 395, 15 from 512), compared with the design's armor plating index (design byte 0x1e; 0 counts as 1): d = gun class - plating.
            d == 0 -> 10; -4 <= d <= 3 -> 8; -8 <= d <= 5 -> 6; -13 <= d <= 9 -> 4; else 1.   (armor that matches the biggest gun is what the game wants)
ANTI-AIR    L = the highest u8 at system record +0x35 (u16[26] >> 8, the extra auto-fire slots: Auto Countermeasures) over the ten system slots; base = 0 for L 0, 2 for L 1, 4 for L >= 2.
            n = number of mounts whose part has byte 4 == 1 and u16[67] bit 3 (8); n bonus: 0 -> 0, 1..5 -> 1, 6..10 -> 2, 11..19 -> 4, 20 and more -> 5.
            e = 1 when some such mount has slot category b8 >= 6 - L (a weapon in one of the extra auto-fire categories), else 0.   raw = base + bonus + e
            raw >= 9 -> 10, >= 7 -> 8, >= 5 -> 6, >= 2 -> 4, else 1.
RESPONSE    L as above; s = 1 when some system has (record byte +0x3b & 7) != 0; for the weapons (byte 4 == 1) the u16[67] bits: 2 (anti-sub), 8 (anti-air), 1 (anti-ship), 0x60 (other);
            e as above.  raw = s + e + 2 * [bit 2] + 2 * [bit 8] + 2 * [bit 1] + 2 * [bits 0x60]; minus 2 unless all of the bits 2, 8 and 1 are present (one weapon of each kind).
            then the same raw -> score table as the anti-air one.
COMMAND     (COMMAND + RADAR + SONAR) / 3 (truncated): >= 95 -> 10, >= 80 -> 8, >= 50 -> 6, >= 20 -> 4, else 1.
MOBILITY    the final speed (kt) against four limits by the hull class: DD, CA and the class-3 hulls 10 / 20 / 35 / 50; BB and classes 4 / 5 10 / 20 / 30 / 40; SS 10 / 18 / 26 / 35;
            speed below the first limit -> 1, then 4, 6, 8, and 10 from the last limit up.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
import designer_vp as V
import designer_stats as DS

CLASS_OF = {13: 0, 14: 1, 15: 2, 0x13: 3, 0x10: 4, 0x11: 5, 0x12: 6}      # hull byte 5 -> class index (0x1aa500)
LIMITS = {0: (10, 20, 35, 50), 1: (10, 20, 35, 50), 2: (10, 20, 30, 40), 3: (10, 20, 35, 50), 4: (10, 20, 30, 40), 5: (10, 20, 30, 40), 6: (10, 18, 26, 35)}
GUN_CLASS = [(512, 15), (395, 14), (295, 13), (215, 12), (181, 11), (151, 10), (124, 9), (102, 8), (49, 7), (37, 6), (19, 5), (11, 4), (9, 3), (7, 2)]
GRADES = (1, 4, 6, 8, 10)

def barrel_factor(b):
    """0x1f4cd0: the signed byte at mount +0xb (barrels - 1)."""
    return b + 1 if 0 <= b <= 4 else 7

def raw_score(raw):
    return 10 if raw >= 9 else 8 if raw >= 7 else 6 if raw >= 5 else 4 if raw >= 2 else 1

class Rank:
    def __init__(self):
        self.S = DS.Stats(); self.T = self.S.T
        h = V._dat(7); self.order = {}      # part id -> row index (the game's lookup 0x1f5520 walks the rows in this order)
        for i in range(1120):
            u = struct.unpack_from('<72H', h, 144 * i)
            self.order.setdefault(u[0], i)

    def evaluate(self, d, st=None):
        """st: the design-screen stats (designer_stats.Stats.compute) - pass the game's own numbers to test the rank functions alone."""
        T, S = self.T, self.S
        st = st or S.compute(d)
        mounts = [m for m in V.mounts(d) if m['id'] in T.parts]
        hull = T.hulls[struct.unpack_from('<H', d, 0x1a)[0]][0]
        nslots = struct.pack('<20H', *hull)[0x20]      # hull byte 0x20: the number of system slots the evaluation reads (0x1f4f80 stops there)
        ids = struct.unpack_from('<10h', d, 0x664)
        sysl = [S.sys[i] for i in ids[:nslots] if i >= 0 and i in S.sys]
        L = max([r[0x35] for r in sysl] + [0])
        # --- the weapon slot categories: representative part (lowest row index) and the barrel factor of the mount that brought it
        reps = {}
        for m in mounts:
            if m['b8'] >= 7: continue
            ix = self.order[m['id']]
            if m['b8'] not in reps or ix < reps[m['b8']][0]:
                reps[m['b8']] = (ix, m['id'], barrel_factor(m['barrels'] - 1))
        def best(skip_kinds):
            b = 0
            for ix, pid, f in reps.values():
                p = T.parts[pid]
                if (p[3] & 255) in skip_kinds: continue
                b = max(b, p[32] * f)
            return b
        off_v = best((3,)); arm_v = best((6, 7))
        off = 10 if off_v >= 10000 else 8 if off_v >= 1000 else 6 if off_v >= 500 else 4 if off_v >= 250 else 1
        gun_class = next((c for lim, c in GUN_CLASS if arm_v >= lim), 1)
        plating = d[0x1e] or 1
        dd = gun_class - plating
        arm = 10 if dd == 0 else 1 if not -13 <= dd <= 9 else 4 if not -8 <= dd <= 5 else 8 if -4 <= dd <= 3 else 6
        # --- anti-air and response
        n = 0; e = 0; bits = 0
        for m in mounts:
            p = T.parts[m['id']]
            if (p[2] & 255) != 1: continue
            if p[67] & 8: n += 1
            b8 = m['b8'] - 256 if m['b8'] > 127 else m['b8']
            if not b8 < 6 - L: e = 1
            bits |= p[67]
        base = 0 if L == 0 else 2 if L == 1 else 4
        bonus = 0 if n == 0 else 1 if n <= 5 else 2 if n <= 10 else 4 if n <= 19 else 5
        aa = raw_score(base + bonus + e)
        # response: its own pass over the same weapons (e = any weapon in an extra auto-fire category, whichever kind)
        s = 1 if any(r[0x3b] & 7 for r in sysl) else 0
        raw = s + e + (2 if bits & 2 else 0) + (2 if bits & 8 else 0) + (2 if bits & 1 else 0) + (2 if bits & 0x60 else 0)
        if not (bits & 2 and bits & 8 and bits & 1): raw -= 2
        resp = raw_score(raw)
        # --- command, mobility
        avg = int((st['command'] + st['radar'] + st['sonar']) / 3)
        cmd = 10 if avg >= 95 else 8 if avg >= 80 else 6 if avg >= 50 else 4 if avg >= 20 else 1
        cls = CLASS_OF.get(hull[2] >> 8, 0)
        k = sum(1 for x in LIMITS[cls] if st['speed'] >= x)
        mob = GRADES[k]
        total = off + aa + arm + resp + cmd + mob
        idx = 0 if total >= 60 else 1 if total >= 50 else 2 if total >= 30 else 3 if total >= 10 else 4
        return dict(off=off, aa=aa, arm=arm, resp=resp, cmd=cmd, mob=mob, total=total, idx=idx,
                    detail=dict(off_value=off_v, arm_value=arm_v, gun_class=gun_class, plating=plating, L=L, aa_count=n, extra_slot=e, response_bits=bits, command_avg=avg, speed=st['speed'], hull_class=cls))

if __name__ == '__main__':
    R = Rank()
    import designer_emu as DE
    ds = DE.designs()
    if len(sys.argv) > 1 and sys.argv[1] == 'table':
        for k, d in enumerate(ds): r = R.evaluate(d); print(k, {a: r[a] for a in ('off', 'aa', 'arm', 'resp', 'cmd', 'mob', 'total', 'idx')})
        sys.exit()
    c = DE.make_cpu(); DSG, ST = 0x1200000, 0x1210000
    for a in (0x1f7b60, 0x1f7d28, 0x2804cc): c.hooks[a] = lambda cpu: None
    s8 = lambda v: v - 256 if v & 128 else v
    ok = {k: 0 for k in ('off', 'aa', 'arm', 'resp', 'cmd', 'mob', 'idx')}; bad = []
    for k, d in enumerate(ds):
        c.put(DSG, d); c.put(ST, b'\0' * 0x300); c.run(0x1f4f10, (ST, DSG), max_steps=8000000)
        g = {}
        for name, a in (('mob', 0x1f6100), ('off', 0x1f5a58), ('aa', 0x1f5b10), ('arm', 0x1f5cd8), ('resp', 0x1f5e68), ('cmd', 0x1f6098)):
            c.run(a, (ST, DSG)); g[name] = s8(c.r[2] & 255)
        g['idx'] = c.rd(ST + 0x15, 1)
        r = R.evaluate(d)
        for name in ok:
            if r[name] == g[name]: ok[name] += 1
            else: bad.append((k, name, r[name], g[name]))
    print('port vs game over %d designs:' % len(ds), ok)
    for x in bad[:30]: print(x)
