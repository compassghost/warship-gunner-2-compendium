"""Build web/tree.json for the tech tree viewer from the game's own data only: positions, costs, turns, labels, prerequisites, unlock conditions, and the stat panels
(hull, engine, system, facility and aircraft stats via tools/game_stats.py). Also writes web/weapon_stats.json. No third-party data is read.
Run order:  python tools/decode_rd_tree.py ; python tools/full_names.py ; python tools/build_tree.py      (needs iso_extract/DAT.BIN)"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(__file__))
import wg2, dat_tables as dt, full_names, game_stats as gs

ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.environ.get('WG2_OUT') or os.path.join(ROOT, 'web')      # output folder (default web/)
os.makedirs(OUT, exist_ok=True)
CATEGORIES = [('ARTILLERY', ['MAIN', 'AMMO', 'HI ANGLE', 'MACHINE', 'RAPID', 'PROTO']),
              ('LAUNCHERS', ['TORPEDO', 'EXPLOSIVE', 'MISSILE', 'ROCKET', 'FLARE']),
              ('HIGH TECH', ['ORGANIC', 'OPTICAL', 'PLASMA', 'MAGNETIC', 'PULSE', 'A-MATTER']),
              ('HULLS', ['HULLS']),
              ('STRUCTURES', ['BRIDGE', 'AFT', 'FACILITY']),
              ('ENGINE', ['POWER', 'ROTATION', 'PURGE']),
              ('SYSTEMS', ['ATTACK', 'DEFENSE', 'STEERING', 'ENIGMA']),
              ('AIRCRAFT', ['FIGHTER', 'INTERCEPT', 'BOMBER', 'SCOUT', 'HELI', 'SPECIAL'])]

ROMAN = {'Ⅰ': 'I', 'Ⅱ': 'II', 'Ⅲ': 'III', 'Ⅳ': 'IV', 'Ⅴ': 'V', 'Ⅵ': 'VI', 'Ⅶ': 'VII', 'Ⅷ': 'VIII', 'Ⅸ': 'IX', 'Ⅹ': 'X'}

def ascii_roman(s):
    """The game stores Roman numerals as single Unicode characters that many fonts draw in a serif face; use plain letters on the web."""
    return re.sub('[Ⅰ-Ⅹ]', lambda m: ROMAN[m.group(0)], s)

def clean(s):
    s = re.sub(r'#[A-Za-z]\d*', '', s)       # game colour/format codes
    s = s.replace('#=', '').replace('~', '')
    return ascii_roman(s).strip()


GROUP_NAMES = ['MAIN', 'AMMO', 'HI ANGLE', 'MACHINE', 'RAPID', 'PROTO', 'TORPEDO', 'EXPLOSIVE', 'MISSILE', 'ROCKET', 'FLARE', 'ORGANIC', 'OPTICAL',
               'PLASMA', 'MAGNETIC', 'PULSE', 'A-MATTER', 'HULLS', 'BRIDGE', 'AFT', 'FACILITY', 'POWER', 'ROTATION', 'PURGE', 'ATTACK', 'DEFENSE',
               'STEERING', 'ENIGMA', 'FIGHTER', 'INTERCEPT', 'BOMBER', 'SCOUT', 'HELI', 'SPECIAL']

def medal_name(m, names):
    """Index into the game's 84-entry medal/flag status table: 0-15 Silver Swan classes, 16-55 service medals, 56+ flags (in DAT entry 14 order)."""
    if m < 56: return ('Medal', names[995 + m])
    return ('Flag', names[1051 + (m - 56)])

def conditions(c, labmap, names):
    """Decode the unlock-condition bits the game tests (evaluator at 0x214EA0): low byte of field 16 is a bit mask."""
    f16, f17, f18, f19, f20, f21 = c['cond_raw']
    flags = f16 & 0xff; out = []
    if flags & 0x20 and 0 <= f18 < 34:
        out.append(dict(kind='chip', text='Another chip must be developed first', group=GROUP_NAMES[f18], idx=f19, label=labmap.get((GROUP_NAMES[f18], f19), '?')))
    if flags & 0x10:
        kind, nm = medal_name(f17 & 0xff, names)
        out.append(dict(kind='medal', text=f'{kind} required: {nm}'))
    if flags & 0x40:
        out.append(dict(kind='progress', text='Unknown factor'))
    if flags & 0x80:
        out.append(dict(kind='recovered', text='The matching part or plan must be recovered from the enemy'))
    if flags & 0x08:
        out.append(dict(kind='counter', text=f'Electronic Blueprint {f16 >> 8}'))      # project owner's reading: the counter is a collected Electronic Blueprint
    xo = flags & 7
    if xo:
        blocked = [k for k, b in enumerate((1, 2, 4)) if xo & b]
        allowed = [k for k in range(3) if k not in blocked]
        out.append(dict(kind='route', text='Only on captain route ' + ' or '.join(str(k) for k in allowed) + ' (route numbers 0-2 are as stored in the save)'))
    return out
def main():
    f = open(os.path.join(ROOT, 'iso_extract/DAT.BIN'), 'rb'); idx = wg2.read_index(f)
    o, s = idx[34]; f.seek(o)
    labels = dt.strings(wg2.decompress(f.read(s))[0])
    o14, s14 = idx[14]; f.seek(o14)
    medal_names = dt.strings(wg2.decompress(f.read(s14))[0])
    fulls = full_names.compose()
    astats = gs.aircraft_stats()
    raw = json.load(open(os.path.join(ROOT, 'data/tree_raw.json')))
    labmap = {(c['group_name'], c['index']): clean(labels[c['raw_name_fields'][0]]) for c in raw['chips'] if c['raw_name_fields'][0] < len(labels)}
    bygroup = {}
    for c in raw['chips']: bygroup.setdefault(c['group_name'], []).append(c)
    gl = {}
    for gname, chips in bygroup.items():
        amap = {c['index']: set(c['ancestors']) for c in chips}
        out = []
        for c in chips:
            if c['index'] > 0 and c['x'] is None: continue      # chips the game never places on the tree
            anc = set(c['ancestors'])
            direct = sorted(a for a in anc if not any(a in amap[b] for b in anc if b != a))
            lab = clean(labels[c['raw_name_fields'][0]]) if c['raw_name_fields'][0] < len(labels) else '?'
            out.append(dict(i=c['index'], label=lab, x=c['x'], y=c['y'], cost=c['cost'], turns=c['turns'], hidden=c['hidden'],
                            kind=c['type'], prereq=direct, anc=sorted(anc), conds=conditions(c, labmap, medal_names), item=c['item_id'], full=fulls.get(c['group_name'] + ':' + str(c['index'])) or lab, stats=astats.get((c['group_name'], c['index']))))
        kids = {}
        for c in out:
            for p in c['prereq']: kids.setdefault(p, []).append(c)
        for c in out:
            if c['i'] <= 0: continue
            if gname in ('ATTACK', 'DEFENSE', 'STEERING', 'ENIGMA'):
                si = gs.system_block(gname, c['i'])
                if si: c['sys'] = si
            elif gname == 'FACILITY':
                si = gs.facility_block(c['i'])
                if si: c['sys'] = si
            elif gname in ('POWER', 'ROTATION', 'PURGE'):
                en = gs.engine_block(gname, c['i'], c['full'], kids.get(c['i'], []))
                if en: c['eng'] = en
            elif gname == 'HULLS':
                hs = gs.hull_block(c['full'])
                if hs: c['eng'] = hs        # sub-types: caliber / barrel chips (kinds 2, 3) and nation / ship-class chips (kind 1 hanging off a level chip, kind 4)
        kind_by = {c['i']: c['kind'] for c in out}
        for c in out:
            p = c['prereq'][0] if c['prereq'] else None
            c['sub'] = c['kind'] in (2, 3) or (c['kind'] == 1 and p is not None and kind_by.get(p) == 4)
        gl[gname] = out
    cats = []
    for cname, groups in CATEGORIES:
        cats.append(dict(name=cname, groups=[dict(name=g, chips=gl[g]) for g in groups]))
    json.dump(dict(categories=cats, source='Decoded from DAT.BIN (R&D master table); labels from the game label table'),
              open(os.path.join(OUT, 'tree.json'), 'w', encoding='utf8'), separators=(',', ':'), ensure_ascii=False)
    ws = gs.weapon_stats(); json.dump(ws, open(os.path.join(OUT, 'weapon_stats.json'), 'w', encoding='utf8'), separators=(',', ':'))
    print('weapon stat rows:', len(ws))
    print('chips written:', sum(len(g['chips']) for c in cats for g in c['groups']))

main()







