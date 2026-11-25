"""Decode Warship Gunner 2's weather / time-of-day / sea-palette data from the game files and EXECUTE the game's own
blender (SLUS_213.87 0x148b78 + 0x146390) on it.  Writes data/weather.json.  See notes/weather.md for what is confirmed.

Sources (all verified in the executable, see the note):
  DAT.BIN entry 2   = the weather / light table, loaded by 0x103ba0 (file id 6002) and relocated by its header
  DAT.BIN entry 4   = map table (40-byte records from byte 612): bytes +36 / +37 / +38 are read by 0x104518
  MAP.BIN 16..22    = sea colour sets: 24 palettes of 1024 B = 3 weather sets x 8 time phases (loaded by 0x103590)
  BEV.BIN 206..281  = mission scripts: record kind 3 = start time (hour, minute), kind 4 = second time
The time-of-day evaluation is done by running the game's own MIPS code in tools/mips_emu.py, not by a re-implementation.
Usage:  python tools/decode_weather.py     (writes data/weather.json)
"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import mips_emu as E
import model_entities as me
import bev_script as bs

ROOT = os.path.join(os.path.dirname(__file__), '..')
GP = 0x2b64f0
DAT2_BASE = 0x1000000        # where we place DAT 2 in the emulator's memory (any free address)
OUT = 0x2000000              # output struct of 0x148b78

# DAT 2 header: (u32 count, u32 offset) pairs from byte 0x10, offset = value at 0x14 + 8k.  Pointer globals set by 0x103ba0:
GLOBALS = [  # (global address, header offset of the pointer, name, record size, record count)
    (0x2ae678, 0x34, 'sun_height_limits', 32, 3),      # 3 sets x 8 floats (radians) - used by 0x14682c, role not decoded
    (0x2ae67c, 0x3c, 'phase_colours', 36, 24),         # 3 sets x 8 phases x 9 colour dwords (B,G,R,A)
    (0x2ae680, 0x44, 'time_keys', 3, 14),              # (hour, minute, phase) triples
    (0x2ae684, 0x4c, 'colour_gain_pairs', 72, 13),     # per weather 9 x (float, float)
    (0x2ae688, 0x54, 'day_colours', 36, 13),
    (0x2ae68c, 0x74, 'night_colours', 36, 13),
    (0x2ae690, 0x5c, 'evening_colours', 36, 5),        # only weathers 0-4
    (0x2ae694, 0x64, 'morning_colours', 36, 5),        # only weathers 0-4
    (0x2ae698, 0x6c, 'day_floats', 28, 13),
    (0x2ae69c, 0x7c, 'night_floats', 28, 13),
    (0x2ae6a0, 0x8c, 'weather_bytes_a', 2, 13),
    (0x2ae6a4, 0x84, 'weather_bytes_b', 2, 13),
    (0x2ae6a8, 0x94, 'particle_sprites', 10, 9),
]


def u32(d, o): return struct.unpack_from('<I', d, o)[0]


def colour(b):   # 4 bytes B,G,R,x (the game's order, same as its palettes) -> [R,G,B]
    return [b[2], b[1], b[0]]


def make_cpu(dat2):
    c = E.CPU()
    c.put(DAT2_BASE, dat2)
    c.dat2 = dat2
    c.r[28] = GP
    for addr, ho, *_ in GLOBALS:
        c.wr(addr, 4, DAT2_BASE + u32(dat2, ho))
    def memcpy(cpu): cpu.put(cpu.r[4], cpu.get(cpu.r[5], cpu.r[6]))
    c.hooks[0x27f874] = memcpy
    return c


def evaluate(c, w, hour, minute, light_set=0, night_gain=4, dark_adj=1, clock_frames=0):
    # night_gain = 0x2b27c6 = stage+0x14, which the stage init 0x137100 sets to 4 (no mission overrides it, kind 6 is unused);
    # dark_adj = 0x2b284b, which the briefing code 0x1d0848 sets to 1 when 27c6 >= 4 -> night colours x min(2*(4+1),12)/12 = 10/12
    """Run the game's 0x148b78 for weather w at the clock hour:minute (state globals: 0x2b27c0 hour, 0x2b27bf minute,
    0x2b27b8 frame counter, 0x2b285e = map light set, 0x2b27c6 / 0x2b284b = darkness add-ons, left 0)."""
    c.wr(0x2b27c0, 1, hour); c.wr(0x2b27bf, 1, minute); c.wr(0x2b27be, 1, 0); c.wr(0x2b27b8, 4, clock_frames)
    c.wr(0x2b285e, 1, light_set); c.wr(0x2b27c6, 1, night_gain); c.wr(0x2b284b, 1, dark_adj)
    c.wr(0x2b27c5, 1, 0); c.wr(0x2b27ae, 2, 0)
    # sun light level (0x149a00): min(1024, distance in clock units to 05:45 or 18:15 * 1024 / 6000): 0 at the two switch times, full 1 game minute away
    T = hour * 360000 + minute * 6000 + clock_frames * 100 // 1920
    c.wr(GP - 0x7188, 4, min(0x400, min(abs(T - 2070000), abs(T - 6570000)) * 1024 // 6000))
    # the 9 (float, float) colour-adjust pairs the game keeps at 0x2c1318 (filled by 0x147de0 from DAT 2's weather gain table x 1.0)
    goff = u32(c.dat2, 0x4c) + 72 * w
    c.put(0x2c1318, c.dat2[goff:goff + 72])
    c.run(0x148b78, (OUT, w))
    o = c.get(OUT, 0xd0)
    ph_a = c.rd(GP - 0x710c, 4); ph_b = c.rd(GP - 0x7108, 4); f = c.rd(GP - 0x7104, 4)
    return dict(
        colour0=colour(o[0:4]), flash_colour=colour(o[4:8]), colour2=colour(o[8:12]),
        floats=[round(x, 4) for x in struct.unpack_from('<7f', o, 0xc)] ,
        gains=[round(x, 4) for x in struct.unpack_from('<9f', o, 0x20)],
        phase_a=ph_a, phase_b=ph_b, blend=f,
        palette_set=struct.unpack_from('<b', o, 0xb4)[0],
        light9=[colour(o[0x90 + 4 * i:0x94 + 4 * i]) for i in range(9)],
    )


def parse_tables(dat2):
    t = {}
    for addr, ho, name, sz, n in GLOBALS:
        off = u32(dat2, ho)
        t[name] = (off, sz, n)
    return t


def main():
    dat2 = me.Arc('DAT').get(2)
    T = parse_tables(dat2)
    out = {'source': {'DAT': 2, 'note': 'see notes/weather.md'}}

    # --- time key table: (hour, minute, phase)
    off, _, n = T['time_keys']
    keys = [tuple(dat2[off + 3 * i:off + 3 * i + 3]) for i in range(13)]
    out['time_keys'] = [dict(hour=h, minute=m, phase=p) for h, m, p in keys]

    # --- raw 13-weather record tables
    def rec36(name, n):
        off, sz, _ = T[name]
        res = []
        for i in range(n):
            r = dat2[off + 36 * i:off + 36 * i + 36]
            res.append(dict(colour0=colour(r[0:4]), colour1_flash=colour(r[4:8]), colour2=colour(r[8:12]),
                            colour3=colour(r[12:15]), byte3_extra=r[15],
                            palette_set=struct.unpack_from('<i', r, 16)[0], d5=struct.unpack_from('<i', r, 20)[0],
                            d6=struct.unpack_from('<i', r, 24)[0], d7=struct.unpack_from('<i', r, 28)[0],
                            d8_hex=r[32:36].hex()))
        return res
    def rec28(name, n):
        off, sz, _ = T[name]
        return [[round(x, 4) for x in struct.unpack_from('<7f', dat2, off + 28 * i)] for i in range(n)]
    out['tables'] = {
        'day_colours': rec36('day_colours', 13), 'night_colours': rec36('night_colours', 13),
        'evening_colours_w0_4': rec36('evening_colours', 5), 'morning_colours_w0_4': rec36('morning_colours', 5),
        'day_floats': rec28('day_floats', 13), 'night_floats': rec28('night_floats', 13),
        'colour_gain_pairs': [[round(x, 4) for x in struct.unpack_from('<18f', dat2, T['colour_gain_pairs'][0] + 72 * i)] for i in range(13)],
        'sun_height_limits_rad': [[round(x, 4) for x in struct.unpack_from('<8f', dat2, T['sun_height_limits'][0] + 32 * s)] for s in range(3)],
        'phase_colours': [[[colour(dat2[T['phase_colours'][0] + 288 * s + 36 * p + 4 * k:][:4]) for k in range(9)] for p in range(8)] for s in range(3)],
    }

    # --- run the game's routine: a timeline for every weather, light set 0..2, every 10 minutes
    c = make_cpu(dat2)
    timeline = {}
    for ls in range(3):
        for w in range(13):
            rows = []
            for minutes in range(0, 24 * 60, 10):
                r = evaluate(c, w, minutes // 60, minutes % 60, ls)
                r['t'] = '%02d:%02d' % (minutes // 60, minutes % 60)
                rows.append(r)
            timeline['set%d_weather%d' % (ls, w)] = rows
    out['timeline'] = timeline

    # --- verification: the emulated function reproduces the raw day / night table values exactly
    chk = []
    for w in range(13):
        d = evaluate(c, w, 12, 0); n = evaluate(c, w, 2, 0)
        dr = out['tables']['day_colours'][w]; nr = out['tables']['night_colours'][w]
        okd = d['colour0'] == dr['colour0'] and d['colour2'] == dr['colour2']
        okn = all(abs(n[k][i] - nr[k][i] * 10 / 12) <= 1 for k in ('colour0', 'colour2') for i in range(3))   # 27c6 4 + 284b 1 -> x 10/12
        chk.append((w, okd, okn))
    out['verification'] = {'noon_equals_day_table_and_02h_equals_night_table_x_10/12': chk}

    # --- sea palettes: MAP 15..22 = 24 palettes (3 sets x 8 phases)
    map_arc = me.Arc('MAP')
    # verify the palette blend (0x146318: palette = A + ((B - A) * f >> 10) per byte) by running the game's routine
    blk = map_arc.get(16)
    c.put(0x3000000, blk)
    pal_ok = True
    for (pa, pb, f, st) in ((1, 2, 300, 0), (3, 4, 1024, 1), (7, 0, 511, 2), (5, 5, 0, 0)):
        c.wr(GP - 0x710c, 4, pa); c.wr(GP - 0x7108, 4, pb); c.wr(GP - 0x7104, 4, f)
        c.run(0x146318, (0x3000000 + st * 8192, 0x3100000))
        got = c.get(0x3100000, 1024)
        A = blk[st * 8192 + pa * 1024:][:1024]; B = blk[st * 8192 + pb * 1024:][:1024]
        if pa == pb: exp = A
        elif f == 1024: exp = B
        else: exp = bytes((a + int((b - a) * f / 1024)) & 255 for a, b in zip(A, B))   # truncating division, as the game does
        pal_ok &= (got == exp)
    out['verification']['sea_palette_blend_matches_game_routine_0x146318'] = pal_ok
    out['sea_palette_files'] = {str(n): len(map_arc.get(n)) for n in range(15, 24)}

    # --- map table (DAT 4)
    d4 = me.Arc('DAT').get(4)
    maps = []
    for i in range(75):
        r = d4[612 + 40 * i:612 + 40 * i + 40]
        fl = struct.unpack_from('<H', r, 38)[0]
        maps.append(dict(record=i, byte36=r[36], light_set=r[37], sea_file_index=r[38], flags_hi=fl >> 8,
                         sea_palette_map_entry=0x10 + r[38], floats=[round(x, 3) for x in struct.unpack_from('<2f', r, 28)]))
    out['maps'] = maps

    # --- missions: start time (kind 3) and second time (kind 4)
    ms = []
    for e in range(206, 282):
        m = bs.mission(e)
        k = {r['kind']: r['par'] for r in m['blocks'][0]['recs'] if r['kind'] in (3, 4)}
        ms.append(dict(entry=e, code=m['code'], start=[k[3][0], k[3][1]], second_time=[k[4][0], k[4][1]]))
    # --- briefing START label: the game's 0x138658(hour, DAT 18) -> index; text = DAT 18 string 0x12 + index (0x1c0998 reads entry k-1)
    d18 = me.Arc('DAT').get(18)
    c.put(0x3200000, d18)
    def s18(k):
        o = u32(d18, 0x14 + 8 * k); return d18[o:d18.index(b'\0', o)].decode()
    label = {h: c.run(0x138658, (h, 0x3200000)) for h in range(24)}
    out['briefing_label'] = {'thresholds_dat18': list(d18[u32(d18, 0x404):u32(d18, 0x404) + 4]),
                             'by_hour': {h: s18(0x12 + v) for h, v in label.items()}}
    for m in ms: m['briefing_label'] = s18(0x12 + label[m['start'][0] % 24])
    # per-mission map: DAT 2 section (header 0xe4, 84 bytes) indexed by mission number (0x2b28a4; mission n = BEV 205 + n), read by the hooks (0x1e7078)
    mtab = dat2[u32(dat2, 0xe4):u32(dat2, 0xe4) + 84]
    for m in ms:
        n = m['entry'] - 205; mp = mtab[n]; r = maps[mp]
        m['map_record'] = mp; m['light_set'] = r['light_set']; m['sea_palette_map_entry'] = r['sea_palette_map_entry']
        m['haze_band_byte36'] = r['byte36']; m['sky_colour_adjust'] = r['floats']   # map floats +28 / +32 -> gp-0x7178 / -0x7174 (multipliers of the 9 colour-adjust pairs)
        m['stage_weights'] = '{weather 0: 100} (BEV 204 weight table empty; game parser 0x1379e0 run in the emulator)'
    # --- event-VM scripts: kind-22 nodes set hour / minute / weather (tools/event_weather.py, notes/weather.md seventh pass)
    import event_weather as ew
    exe_b = open(E.EXE, 'rb').read()
    ev_table, ev_weather, ev_per = ew.decode([bs.mission(m['entry']) for m in ms], exe_b)
    out['event_weather'] = {
        'note': 'event id -> event script (table 0x28d648); kind-22 commands in that script, read after loading it with the game loader '
                '0x130268 in the emulator. set_on_load = what the game code called while loading (0x147da0(weather, fade)). '
                'steps[0] is applied on load (events 4/8 in 0x134498); later steps on event 0x200. Timing caveat: the stage-start weather '
                'pick (0x1048b0 -> 0x104f60 -> 0x14c468) runs after the pre-load in the same routine and writes the weather byte from the '
                'stage weights on a first start; whether the loaded weather survives that from frame 1 is not settled.',
        'events': {str(k): v for k, v in sorted(ev_weather.items())},
        'event_table': [list(t) for t in ev_table]}
    for m, p in zip(ms, ev_per):
        m['events'] = [e['event'] for e in p['events']]
        steps = [(ev, s) for ev in p['weather_events'] for c in ev_weather[ev]['commands'] for s in c['steps']]
        m['event_weather'] = [dict(event=ev, **s) for ev, s in steps]
        first = [s['weather'] for ev in p['weather_events'] for c in ev_weather[ev]['commands'][:1] for s in c['steps'][:1] if s['weather'] is not None]
        m['weather_from_event_on_load'] = first[0] if first else None
    out['missions'] = ms

    # --- VIEW VESSEL-type screen (0x1f3598, options read by 0x119a20 / 0x119a38, cycled by 0x118050): time option 0-3 -> hour from the
    #     table at 0x2b2050 (label = the same DAT 18 strings 0x12 + option), weather option 0-5 -> weather value (jump table at 0x2a9cf8 + default 7)
    exe = open(E.EXE, 'rb').read()
    hours = list(exe[0x2b2050 - E.LOAD:0x2b2050 - E.LOAD + 4])
    out['vessel_viewer'] = {'times': [[h, s18(0x12 + i)] for i, h in enumerate(hours)], 'weathers': [0, 3, 6, 10, 12, 7],
                            'note': 'clock frozen (0x2b27bc = 0 at 0x1f3420); which screen this is (vessel viewer is my reading) not confirmed'}

    # --- decoded rendering facts (see notes/weather.md, third pass)
    out['rendering'] = {
        'fog_colour': 'phase colour slot 4 (E+0x13c) -> GS FOGCOL (0x2252bc)',
        'fog': 'linear, F = 255*(far - z)/(far - near); near = 0 (forced at 0x1482b4), far = float 3 (E+0x144); z in map units (1 = 4096 model units)',
        'sky_stops_deg': [round(x * 57.29578, 2) for x in struct.unpack_from('<8f', dat2, T['sun_height_limits'][0])],
        'sky': '2D vertical gradient (0x146660): colour stop i = phase colour slot i at elevation sky_stops_deg[i] (per light set); above the first stop = slot 0',
        'ambient': '(colour0 + flash colour) * float4 / 128 per channel (0x225150)',
        'stars': 'drawn when the clock is before 06:00 or after 18:00 (0x146a98)',
        'effects': {'type_1_weathers_8_10': 'mist / fog layer (density byte 6/12/24, fog far 400) - name inferred',
                    'type_2_weathers_5_7': 'rain, 300/1000/3000 drops, speed 1.0 (0x129558)',
                    'type_3_weathers_11_12': 'slow particles 800/3000 at speed 0.2 - probably snow (inferred)',
                    'lightning': 'weather 4 starts the lightning state (0x147ed0); weathers 4 and 7 run the lightning branch of 0x1478a8 - "thunder" inferred'},
    }

    # --- web export for the dock page: the dock map records (67-74) use light set 0 and sea file MAP 16. All 13 weathers,
    #     every 2 game minutes, produced by the game's own routine (which weather the dock shows is NOT decoded).
    web = os.path.join(ROOT, 'web', 'water')
    allw = []
    for w in range(13):
        rows = []
        for minutes in range(0, 1440, 2):
            r = evaluate(c, w, minutes // 60, minutes % 60, 0)
            rows.append([r['phase_a'], r['phase_b'], r['blend'], r['palette_set'], r['colour0'], r['flash_colour'], r['colour2'], r['floats'], r['light9']])
        allw.append(rows)
    with open(os.path.join(web, 'clock_all.json'), 'w') as f:
        json.dump({'note': 'light set 0 (dock), every 2 game minutes; weathers[w][minute/2] = [phase_a, phase_b, blend(0..1024), sea palette set (-1 = unchanged), colour0, flash, colour2, floats7, light9 (R,G,B)]; see notes/weather.md',
                   'step': 2, 'sky_stops_deg': out['rendering']['sky_stops_deg'], 'weathers': allw,
                   'missions': [[m['code'], m['start'][0], m['start'][1], m['briefing_label'], m['weather_from_event_on_load'],
                                 [[e['event'], e['weather'], e['fade_s']] for e in m['event_weather'] if e['weather'] is not None]] for m in ms],
                   'vessel_viewer': out['vessel_viewer'],
                   # weather effects (record dword 6 = type 0 none / 1 mist / 2 rain / 3 slow particles, dword 7 = count (sign dropped),
                   # dword 8 = particle colour B,G,R,A (0x80 = 1.0), byte 15 = mist density); day and night records; fall speed 1.0 / 0.2 from the code (third pass)
                   'effects': [[out['tables']['day_colours'][w]['d6'], abs(out['tables']['day_colours'][w]['d7']),
                                list(bytes.fromhex(out['tables']['day_colours'][w]['d8_hex'])), list(bytes.fromhex(out['tables']['night_colours'][w]['d8_hex'])),
                                out['tables']['day_colours'][w]['byte3_extra'], {2: 1.0, 3: 0.2}.get(out['tables']['day_colours'][w]['d6']),
                                w in (4, 7)] for w in range(13)]}, f, separators=(',', ':'))
    with open(os.path.join(web, 'sea_map16.bin'), 'wb') as f: f.write(map_arc.get(16))

    p = os.path.join(ROOT, 'data', 'weather.json')
    with open(p, 'w') as f: json.dump(out, f, separators=(',', ':'))
    print('wrote', p, os.path.getsize(p), 'bytes')
    print('verification', chk)


if __name__ == '__main__':
    main()
