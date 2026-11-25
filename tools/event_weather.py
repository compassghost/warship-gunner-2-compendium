"""Per-mission weather / clock commands in the event-VM scripts (decoded 2026-11-17, see notes/weather.md "Seventh pass").

How the game does it (SLUS_213.87, all read in the code and checked by running it in tools/mips_emu.py):
  * Mission scripts (BEV 206+n) contain records kind 27 / sub 11 whose first parameter is an EVENT id (660, 661, ...).
  * The table at 0x28d648 (u16 triplets: event id, file id, flag; ends at event -1) maps an event id to an event-VM script
    file (BEV 305-359).  Lookups: 0x13e1d8 and the record converter at 0x139124.
  * At stage load, hook(0) -> 0x10dc48 -> 0x139570 pre-loads every event script of the mission with 0x130268(file, -2)
    (parser 0x12a000).  The VM's node callback 0x1314b0 sends node kind 22 to 0x134498:
      event 4 / 8 (sent while the script is loaded): first child of the node -> hour, minute, weather
      event 0x200 (later step): child [node+0x10] -> hour, minute, weather, fade seconds, value, option
    Child fields (s16 at child+8): +0 ?, +2 hour (<24 or ignored), +4 minute (<60 or ignored), +6 weather (<13 or ignored),
    +8 fade seconds (>0: 0x147da0(weather, s*60), else 0x147da0(weather, 1)), +0xa value -> gp-0x316c, +0xc 1..3 -> 0x2b27c5.
This module loads each event script with the game's own loader in the emulator and reports the kind-22 commands, plus the
weather / clock that the game's code actually set while loading (0x147da0 hooked)."""
import os, sys, struct, io, contextlib
sys.path.insert(0, os.path.dirname(__file__))
import mips_emu as E
import wg2

ROOT = os.path.join(os.path.dirname(__file__), '..')
GP = 0x2b64f0
TABLE = 0x28d648
STUBS = (0x266c78, 0x1033b0, 0x1025b0, 0x228f38)   # texture / model upload (GS packet code the emulator does not run)


def event_table(exe):
    out, a = [], TABLE
    while True:
        ev, fid, flag = struct.unpack_from('<3h', exe, a - E.LOAD)
        if ev < 0: return out
        out.append((ev, fid & 0xffff, flag)); a += 6


class _Loader:
    def __init__(self):
        self.f = open(os.path.join(ROOT, 'iso_extract', 'BEV.BIN'), 'rb'); self.idx = wg2.read_index(self.f)

    def cpu(self):
        c = E.CPU(); c.r[28] = GP
        def load(cpu):
            fid, buf = cpu.r[4], cpu.r[5]
            if not (8000 <= fid < 8000 + len(self.idx)): cpu.r[2] = 0; return
            o, s = self.idx[fid - 8000]; self.f.seek(o); cpu.put(buf, self.f.read(s)); cpu.r[2] = s
        def dec(cpu):
            out, _ = wg2.decompress(cpu.get(cpu.r[4], 0x40000)); cpu.put(cpu.r[5], out); cpu.wr(0x2b2b50, 4, len(out)); cpu.r[2] = len(out)
        c.hooks[0x101228] = load; c.hooks[0x22e640] = dec
        c.hooks[0x27f874] = lambda cpu: cpu.put(cpu.r[4], cpu.get(cpu.r[5], cpu.r[6]))
        c.hooks[0x27f924] = lambda cpu: cpu.put(cpu.r[4], bytes([cpu.r[5] & 255]) * cpu.r[6])
        for a in (0x254c30, 0x254da0, 0x254e88, 0x254e58): c.hooks[a] = lambda cpu: None
        for a in STUBS: c.hooks[a] = lambda cpu: cpu.setr(2, 0)
        c.wr(0x2b28c8, 4, 0x1000000); c.wr(0x2b28cc, 4, 0x1800000); c.wr(0x2b2924, 4, 0x2500000); c.wr(0x70000000, 4, 0x70000100)
        return c

    def script(self, fid):
        """Load event script `fid` the way the stage pre-load does (0x130268(fid, -2)); return the kind-22 commands."""
        c = self.cpu(); calls = []
        c.hooks[0x147da0] = lambda cpu: calls.append([cpu.r[4] & 0xff, cpu.r[5]])
        c.wr(0x2b27c0, 1, 0xee); c.wr(0x2b27bf, 1, 0xee)
        with contextlib.redirect_stdout(io.StringIO()):
            c.wr(GP - 0x3160, 4, 0); c.run(0x1301b0, (), max_steps=5000000)
            try: c.run(0x130268, (fid, 0xfffffffe), max_steps=30000000)
            except NotImplementedError as ex: err = str(ex)   # an unimplemented op after parsing (texture code); nodes are already built
            else: err = None
        task = c.rd(c.rd(GP - 0x74a8, 4), 4)
        nb = struct.unpack('<h', c.get(task + 2, 2))[0]; arr = c.rd(task + 8, 4); cmds = []
        for i in range(nb):
            p = c.rd(arr + 4 * i, 4)
            if c.rd(p, 1) != 0x16: continue
            lst = c.rd(p + 8, 4); steps = []
            for j in range(c.rd(p + 2, 2)):
                q = c.rd(lst + 4 * j, 4)
                f = struct.unpack('<7h', c.get(q + 8, 14))
                steps.append(dict(hour=f[1] if 0 <= f[1] < 24 else None, minute=f[2] if 0 <= f[2] < 60 else None,
                                  weather=f[3] if 0 <= f[3] < 13 else None, fade_s=f[4] if f[4] > 0 else None,
                                  value=f[5] if f[5] not in (0, -1) else None, option=f[6] if 1 <= f[6] <= 3 else None))
            cmds.append(dict(node=i, steps=steps))
        h, m = c.rd(0x2b27c0, 1), c.rd(0x2b27bf, 1)
        return dict(commands=cmds, emulator_stop=err, set_on_load=dict(weather_calls=calls, hour=None if h == 0xee else h, minute=None if m == 0xee else m))


def decode(missions, exe):
    """missions: list of bev_script.mission() dicts (entries 206-281).  Returns (events, per-mission list)."""
    L = _Loader(); table = event_table(exe); by_ev = {ev: (fid, fl) for ev, fid, fl in table}
    events = {}
    for ev, fid, fl in table:
        r = L.script(fid)
        if r['commands']: events[ev] = dict(file=fid, bev_entry=fid - 8000, flag=fl, **r)
    per = []
    for m in missions:
        evs = []
        for bi, b in enumerate(m['blocks']):
            for r in b['recs']:
                if r['kind'] == 27 and r['sub'] == 11:
                    evs.append(dict(event=r['par'][0], block=bi, block_type=b['A'], file=by_ev.get(r['par'][0], (None,))[0]))
        per.append(dict(code=m['code'], events=evs, weather_events=[e['event'] for e in evs if e['event'] in events]))
    return table, events, per


if __name__ == '__main__':
    import bev_script as bs
    exe = open(E.EXE, 'rb').read()
    ms = [bs.mission(e) for e in range(206, 282)]
    table, events, per = decode(ms, exe)
    for ev, d in sorted(events.items()): print(ev, d)
    for p in per:
        if p['weather_events']: print(p['code'], p['weather_events'])
