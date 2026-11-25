"""Design-screen statistics of the game (weight, speed, VP%, armor), decoded from SLUS_213.87 0x19bbe8 / 0x19b650 / 0x19b920 and checked against the game's own code
(run in tools/designer_emu.py with the real DAT tables) for all 530 blueprint designs of DAT entry 26.
  python tools/designer_stats.py            -> self-check (python port vs the executable run in the emulator)
  python tools/designer_stats.py table      -> table of all designs
Formulas (all confirmed by the emulator comparison):
  VP%      = see tools/designer_vp.py (stored in the design at +0x678; the screen recomputes it)
  armor    = plating[idx] * 2 * VP / 100 (integer division), x 80 / 100 (integer) if VP < 54 (core);  idx = design byte 0x1e, plating = DAT 8 + 0x16a8 rows (12 bytes, u32[2])
  weight   = hull.u16[8] + sum(part.u16[17 + barrels - 1]) + sum(system.u16[0x3c]) + armor (+ 200 if design byte 0x67a)
  HP       = boiler.u16[32] * boiler_count * turbine.u16[33] * turbine_count / 100   (turbine_count not applied if the boiler record kind is 0x17; see code)
  speed    = t * (100 - curve[t] / 100) / 100 with t = clamp(trunc(10 * HP / weight), 1, 256) (t = t * 12 / 10 first when the boiler record is kind 0x15), curve = DAT 10 (257 u16),
             then speed += speed * system.u16[0x16] / 100 (sum over the ship's system slots)
  max      = 256 * (1 - 7475/10000) = 64.64 kt  (the 64.6 kt cap)
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
import designer_vp as V

def _dat9():
    return V._dat(9)

class Stats:
    def __init__(self):
        self.T = V.Tables(); self.sys = {}
        b = _dat9()
        for i in range(len(b) // 0x44):
            r = b[0x44 * i:0x44 * (i + 1)]; self.sys[struct.unpack_from('<h', r, 0)[0]] = r

    def systems(self, d):
        ids = struct.unpack_from('<10h', d, 0x664)
        return [self.sys[i] for i in ids if i >= 0 and i in self.sys]

    def compute(self, d):
        T = self.T
        hid = struct.unpack_from('<H', d, 0x1a)[0]
        hull = T.hulls[hid][0]
        mw, hw = hull[6] | (hull[7] << 16), hull[8]      # max weight is a u32 (the Supercarrier: u16[6] 4464 + u16[7] 1 << 16 = 70000)
        mws = list(V.mounts(d))
        parts_w = sum(T.parts[m['id']][17 + m['barrels'] - 1] for m in mws)
        sysl = self.systems(d)
        sys_w = sum(struct.unpack_from('<H', r, 0x3c)[0] for r in sysl)
        sys_speed = sum(struct.unpack_from('<h', r, 0x16)[0] for r in sysl)
        vp = struct.unpack_from('<h', d, 0x678)[0]
        idx = d[0x1e]
        armor = 0
        if idx > 0 and vp > 0:
            armor = T.armor[idx][2] * 2 * vp // 100
            if vp < 54: armor = armor * 80 // 100
        weight = parts_w + sys_w + hw + armor + (200 if d[0x67a] else 0)
        # engine: first group of category 10 (boilers) / 11 (turbines), grouped by (part id, mount b9)
        def first_group(cat):
            groups = {}
            order = []
            for m in mws:
                if m['b8'] == cat:
                    k = (m['id'], m['barrels'])
                    if k not in groups: groups[k] = 0; order.append(k)
                    groups[k] += 1
            return [(k, groups[k]) for k in order]
        bo = first_group(10); tu = first_group(11)
        hp = 0; eff = 0
        if bo:
            (bid, _), nb = bo[0]; brec = T.parts[bid]
            if (brec[3] & 255) == 0x17:
                eff = T.parts[bid][33]
            elif tu:
                (tid, _), nt = tu[0]; eff = T.parts[tid][33] * nt
            hp = brec[32] * nb * eff // 100
        speed = 0.0
        if hp > 0:
            t = int(hp / float(weight) * 10.0)
            if bo and (T.parts[bo[0][0][0]][3] & 255) == 0x15: t = t * 12 // 10      # kind 0x15 (propulsion units): +20 %
            t = max(1, min(256, t))
            speed = t * ((100.0 - T.curve[t] / 100.0) / 100.0)
            speed += speed * sys_speed / 100.0
        # --- command / radar / sonar / purge / endurance / steering (0x19bbe8 + 0x19c1f0) ---
        def first_of(cat):
            for m in mws:
                if m['b8'] == cat: return T.parts[m['id']]
        cmd = rad = son = 0; vent_all = False
        for cat in (20, 21):                      # forward / aft bridge, first mount of each
            p = first_of(cat)
            if p:
                cmd += p[35]; rad += p[41]; son += p[42]
                if p[43]: vent_all = True         # bridge with built-in smokestack (carrier islands): purge 99
        def ssum(off, signed=True):
            return sum(struct.unpack_from('<h' if signed else '<H', r, off)[0] for r in sysl)
        cmd_total = cmd + ssum(0x14) + int(cmd * ssum(0x18) / 100)
        radar = rad + ssum(0xe); sonar = son + ssum(0x10)
        funnels = {}
        for m in mws:
            if m['b8'] == 12: funnels[(m['id'], m['barrels'])] = funnels.get((m['id'], m['barrels']), 0) + 1
        purge = min(99, sum(T.parts[k[0]][34] * n for k, n in funnels.items()))
        if vent_all: purge = 99
        boilers = bo[0][1] if bo and (T.parts[bo[0][0][0]][3] & 255) == 0x14 else 0
        endurance = max(100, hull[9] + ssum(0xc))
        steering = max(1, struct.pack('<20H', *hull)[31] + ssum(0x12))
        return dict(weight=weight, speed=speed, hp=hp, armor=armor, vp=vp, mw=mw, hull_weight=hw, parts_w=parts_w, sys_w=sys_w,
                    command=max(1, cmd_total), radar=max(1, radar), sonar=max(1, sonar), purge=purge, boilers=boilers, unvented=boilers - purge,
                    endurance=endurance, steering=steering)

if __name__ == '__main__':
    import designer_emu as DE
    S = Stats(); ds = DE.designs()
    if len(sys.argv) > 1 and sys.argv[1] == 'table':
        for k, d in enumerate(ds): r = S.compute(d); print(k, r)
        sys.exit()
    c = DE.make_cpu(); DSG, ST = 0x1200000, 0x1210000
    okw = oks = okx = 0; bad = []
    for k, d in enumerate(ds):
        c.put(DSG, d); c.put(ST, b'\0' * 0x100); c.run(0x19bbe8, (ST, DSG), max_steps=5000000)
        b = c.get(ST, 0x60); gw = struct.unpack_from('<I', b, 0)[0]; gs = struct.unpack_from('<f', b, 0x10)[0]
        r = S.compute(d)
        if r['weight'] == gw: okw += 1
        else: bad.append(('w', k, r['weight'], gw))
        if abs(r['speed'] - gs) < 0.01: oks += 1
        else: bad.append(('s', k, round(r['speed'], 2), round(gs, 2)))
        gc, gr, gn = struct.unpack_from('<3h', b, 0x16); gboil, gpurge = struct.unpack_from('<2H', b, 0x1e); gend = struct.unpack_from('<H', b, 4)[0]; gst = b[0x14]
        if (r['command'], r['radar'], r['sonar'], r['boilers'], r['purge'], r['endurance'], r['steering']) == (gc, gr, gn, gboil, gpurge, gend, gst): okx = okx + 1
        else: bad.append(('x', k, (r['command'], r['radar'], r['sonar'], r['boilers'], r['purge'], r['endurance'], r['steering']), (gc, gr, gn, gboil, gpurge, gend, gst)))
    print('weight match %d / %d, speed match %d / %d, command/radar/sonar/purge/endurance/steering match %d / %d' % (okw, len(ds), oks, len(ds), okx, len(ds)))
    for x in bad[:20]: print(x)
