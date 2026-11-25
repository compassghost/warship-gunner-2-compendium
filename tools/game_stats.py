"""Item statistics read straight from the game's tables (no third-party data). Used by tools/build_tree.py.

Part -> tech-tree link. Every record of the part table (DAT entry 7, 144 bytes, first u32 = part id) and of the system table (DAT entry 9, 0x44 bytes)
names the chip it belongs to:  part: u16[30] = group number, u16[31] = chip index in that group (65535 = none);  system record: u16[32] = group, u16[33] = chip.
A chip can have several parts (mount variants, ship classes, nations).  Group numbers are the 34 tree groups in decode_rd_tree.GROUPS order.

Part record (u16 view):  [5] & 255 = bit set of ship classes that may carry it (bit 0 DD, 1 CA, 2 BB, 3 CV, 4 BC, 5 FF, 6 SS), [17..20] = weight for 1..4 barrels (0 = no such mount),
  [32] damage per barrel, [55] rounds per barrel, [56] reload, [57] dispersion, [58] range, [67] target bits (0 sub, 1 surface, 3 air), [68] bit 1 auto-fire, bit 6 underwater,
  boilers: [32] output;  turbines / motors: [33] efficiency;  smokestacks: [34] & 255 purge;  [3] & 255 / u8[6] = part kind (20 boiler, 21 / 22 reactor, 23 gas turbine, 24 sub diesel, 25 / 26 turbine, 27 smokestack).
Hull table (DAT entry 8, 145 x 40 bytes):  u16[0] hull id, u32 at 12 = maximum weight, u16[8] = hull weight, u16[9] = endurance, bytes 30 / 31 / 32 = aircraft / turn radius / system slots.
System table (DAT 9):  u16[30] weight, s16[6..10] endurance, radar, sonar, steering, command, s16[11..23] 13 percent effects (labels = DAT 15 strings 160-172), 1187 + (u16[31] & 255) = DAT 15 description string.
Aircraft (DAT 6 array 0, 132 bytes = 3 x 44): see aircraft_stats().
Everything above was checked against the in-game screens and the published fan guides while decoding; the guides are not used at run time."""
import os, sys, re, struct, collections, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
import wg2, dat_tables as dt
ROOT = os.path.join(os.path.dirname(__file__), '..')
GROUPS = ['MAIN', 'AMMO', 'HI ANGLE', 'MACHINE', 'RAPID', 'PROTO', 'TORPEDO', 'EXPLOSIVE', 'MISSILE', 'ROCKET', 'FLARE', 'ORGANIC', 'OPTICAL',
          'PLASMA', 'MAGNETIC', 'PULSE', 'A-MATTER', 'HULLS', 'BRIDGE', 'AFT', 'FACILITY', 'POWER', 'ROTATION', 'PURGE', 'ATTACK', 'DEFENSE',
          'STEERING', 'ENIGMA', 'FIGHTER', 'INTERCEPT', 'BOMBER', 'SCOUT', 'HELI', 'SPECIAL']
WEAPON_GROUPS = GROUPS[:17]
UNI_ROMAN = {'Ⅰ': 'I', 'Ⅱ': 'II', 'Ⅲ': 'III', 'Ⅳ': 'IV', 'Ⅴ': 'V', 'Ⅵ': 'VI', 'Ⅶ': 'VII', 'Ⅷ': 'VIII', 'Ⅸ': 'IX', 'Ⅹ': 'X'}
_cache = {}

def entry(i):
    if i not in _cache:
        f = open(os.path.join(ROOT, 'iso_extract/DAT.BIN'), 'rb'); idx = wg2.read_index(f); o, s = idx[i]; f.seek(o)
        _cache[i] = wg2.decompress(f.read(s))[0]
        f.close()
    return _cache[i]

def strings(i):
    k = ('s', i)
    if k not in _cache: _cache[k] = dt.strings(entry(i))
    return _cache[k]

def clean(s):
    """Game text -> plain text: colour / button codes out, Roman numeral glyphs to letters, whitespace collapsed."""
    s = re.sub(r'#[YMuiB]\d*', '', s).replace('#=', '').replace('~', '')
    s = unicodedata.normalize('NFKC', s)                  # Roman numeral glyphs and the odd full-width letter in the game text -> plain letters
    return re.sub(r'\s+', ' ', s).strip()

# ---- parts ----------------------------------------------------------------------------------------------------------------------------------------------
def parts():
    """{part id: u16[72]}"""
    if 'parts' not in _cache:
        b = entry(7)
        _cache['parts'] = {struct.unpack_from('<I', b, 144 * i)[0]: struct.unpack_from('<72H', b, 144 * i) for i in range(len(b) // 144)}
    return _cache['parts']

def parts_by_chip():
    """{(group name, chip index): [(part id, u16[72]), ...]} sorted by part id"""
    if 'pbc' not in _cache:
        d = collections.defaultdict(list)
        for pid, u in sorted(parts().items()):
            if u[30] < len(GROUPS) and u[31] not in (0, 0xffff): d[(GROUPS[u[30]], u[31])].append((pid, u))
        _cache['pbc'] = d
    return _cache['pbc']

# ---- weapons --------------------------------------------------------------------------------------------------------------------------------------------
def weapon_stats():
    """{'chip:GROUP:i': dict(att='SA---', mount='dcBVCfs'-style, dam, rld, rnds, dis, rng, wt)} for every weapon chip that has parts.
    The numbers are those of the chip's base mount: 1 barrel, except hi-angle guns and torpedoes whose base mount has 2 (twin) when such a mount exists;
    the mask of ship classes is the union over all mount variants of the chip."""
    out = {}
    for (g, i), ps in parts_by_chip().items():
        if g not in WEAPON_GROUPS: continue
        pid, u = ps[0]
        if not u[56] or not u[58]: continue                    # no reload / range: not a weapon record
        n = 2 if g in ('HI ANGLE', 'TORPEDO') and u[18] else next((k for k in range(1, 5) if u[16 + k]), 1)
        cls = 0; tg = 0; au = 0
        for p, v in ps: cls |= v[5] & 255; tg |= v[67]; au |= v[68]
        out['chip:%s:%d' % (g, i)] = dict(
            att=''.join(c if tg >> b & 1 else '-' for c, b in (('S', 1), ('A', 3), ('U', 0))) + ('a' if au >> 1 & 1 else '-') + ('u' if au >> 6 & 1 else '-'),
            mount=''.join(c if cls >> b & 1 else '-' for b, c in enumerate('dcBVCfs')),
            dam=str(u[32] * n), rld=str(u[56]), rnds=str(u[55] * n), dis=str(u[57]), rng=str(u[58]), wt=str(u[16 + n]))
    return out

# ---- hulls ----------------------------------------------------------------------------------------------------------------------------------------------
NATION = {0: 'Jpn', 1: 'U.S.', 2: 'U.K.', 3: 'Ger'}
TYPE = ['Destroyer', 'Cruiser', 'Battleship', 'Carrier', 'Battlecarrier', 'Submarine', 'Frigate']
SPECIAL = {4000: 'Small Destroyer', 4001: 'Twin-hull Destroyer', 4002: 'Mini Destroyer', 4100: 'Twin-hull Cruiser', 4101: 'Special Cruiser', 4200: 'Drillship',
           4201: 'Duckship', 4202: 'Small Battleship', 4203: 'Twin-hull Battleship', 4204: 'Genuine Drillship', 4300: 'Supercarrier', 4301: 'Shark Submarine', 4400: 'Gigantic Battlecarrier'}
ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
HULL_HEAD = ['Max weight (t)', 'Hull weight (t)', 'Endurance', 'Aircraft', 'Turn radius', 'System slots']

def hull_name(h):
    """hull id -> the name its chip carries: id = nation x 1000 + type x 100 + level - 1; ids from 4000 are the special hulls (700 = Jpn Destroyer VI)."""
    if h in SPECIAL: return SPECIAL[h]
    if h == 700: return 'Jpn Destroyer VI'
    if h // 1000 not in NATION or (h % 1000) // 100 >= len(TYPE) or h % 100 >= len(ROMAN): return None
    return '%s %s %s' % (NATION[h // 1000], TYPE[(h % 1000) // 100], ROMAN[h % 100])

def hull_stats():
    """{lower-case hull name: [max weight, hull weight, endurance, aircraft, turn radius, system slots]}"""
    b = entry(8); out = {}
    for k in range(145):
        r = b[40 * k:40 * k + 40]; u = struct.unpack('<20H', r); name = hull_name(u[0])
        if name: out[name.lower()] = [u[6] | u[7] << 16, u[8], u[9], r[30], r[31], r[32]]
    return out

def hull_block(full):
    r = hull_stats().get(UNI_ROMAN_SUB(full).lower())
    return r and dict(head=HULL_HEAD, rows=[r], note='from the game data', title='Hull stats', vertical=True)

def UNI_ROMAN_SUB(s): return re.sub('[Ⅰ-Ⅹ]', lambda m: UNI_ROMAN[m.group(0)], s).strip()

# ---- engines --------------------------------------------------------------------------------------------------------------------------------------------
CLS = [('DD', 'Destroyer'), ('CA', 'Cruiser'), ('CV', 'Carrier'), ('BB', 'Battleship/Battlecarrier')]
NATIONS = ['Jpn', 'U.S.', 'U.K.', 'Ger']

def engine_block(group, chip, full, children):
    """chip: tree chip dict (i = index); children: chips that hang directly below it (a level chip such as 'Boiler I' has the DD / CA / CV / BB chips below it)."""
    P = parts_by_chip()
    own = P.get((group, chip))
    if group == 'PURGE':
        if not own: return None
        rows = []
        for ci, cname in ((0, 'DD'), (1, 'CA'), (2, 'BB')):
            cells = []
            for n in range(4):
                hit = [u for pid, u in own if 22000 + 1000 * n + 100 * ci <= pid < 22000 + 1000 * n + 100 * ci + 100]
                cells.append('%d / %d' % (hit[0][34] & 255, hit[0][17]) if hit else '–')
            if any(c != '–' for c in cells): rows.append([cname] + cells)
        return dict(head=['Class'] + NATIONS, rows=rows, note='Purge / weight (t) per nation; – = none exists')
    if group == 'ROTATION':
        if not own: return None
        u = own[0][1]
        return dict(head=['Efficiency', 'Weight (t)'], rows=[[u[33], u[17]]], note='Propulsion')
    if group == 'POWER':
        if own:
            u = own[0][1]; kind = u[3] & 255
            if kind == 20: return dict(head=['Output', 'Weight (t)'], rows=[[u[32], u[17]]], note=dict(DD='Destroyer', CA='Cruiser', CV='Carrier', BB='Battleship/Battlecarrier').get(full.split(' ')[0], '') + ' boiler')
            if kind == 24: return dict(head=['Output', 'Weight (t)'], rows=[[u[32], u[17]]], note='Submarine diesel')
            if kind == 23: return dict(head=['Output', 'Efficiency', 'Weight (t)'], rows=[[u[32], u[33], u[17]]], note='Has its own efficiency, no smokestack needed')
            return dict(head=['Output', 'Weight (t)'], rows=[[u[32], u[17]]], note='Needs no smokestack')
        rows = []
        for code, cname in CLS:                                  # a level chip: one row per ship class, taken from the class chips below it
            for ch in children:
                if (full_of(ch)).startswith(code + ' ') and P.get((group, ch['i'])):
                    u = P[(group, ch['i'])][0][1]; rows.append([cname, u[32], u[17]])
        return rows and dict(head=['Class', 'Output', 'Weight (t)'], rows=rows, note='Needs a smokestack')
    return None

def full_of(ch): return ch.get('full') or ch.get('label') or ''

# ---- systems and facilities -----------------------------------------------------------------------------------------------------------------------------
def system_records():
    """{(group name, chip): (record index, u16[34], s16[34])}"""
    if 'sys' not in _cache:
        b = entry(9); d = {}
        for i in range(len(b) // 0x44):
            u = struct.unpack_from('<34H', b, 0x44 * i); s = struct.unpack_from('<34h', b, 0x44 * i)
            if u[32] < len(GROUPS): d[(GROUPS[u[32]], u[33])] = (i, u, s)
        _cache['sys'] = d
    return _cache['sys']

def _label(i):
    m = re.search(r'#M55#=\s*([A-Z\- ]+?)\s*#M57', strings(15)[i])
    return m.group(1).title().replace('Proof', 'proof') if m else strings(15)[i]

def system_block(group, chip):
    """-> dict(desc, effect, weight) from a DAT 9 system record, or None"""
    r = system_records().get((group, chip))
    if not r: return None
    i, u, s = r; S15 = strings(15); out = {}
    d = 1187 + (u[31] & 255)                              # DAT 15 description: text id in the low byte of u16[31], descriptions start at string 1187
    if 0 <= d < len(S15) and S15[d].startswith('#Y4#='): out['desc'] = clean(S15[d])
    eff = ['%s %+d' % (_label(155 + k), s[6 + k]) for k in range(5) if s[6 + k]]
    eff += ['%s %+d%s' % (_label(160 + k), s[11 + k], 'Lv' if k == 12 else '%') for k in range(14) if s[11 + k]]      # 13 percent effects + range increase (the later words are packed level bytes, not decoded)
    if eff: out['effect'] = '; '.join(eff)
    if u[30]: out['weight'] = u[30]
    return out or None

FACILITY_DESC = {1: 1212, 2: 1212, 3: 1346, 4: 1213, 5: 1341, 6: 1342, 7: 1345}      # DAT 15 description string per FACILITY chip

def facility_block(chip):
    ps = parts_by_chip().get(('FACILITY', chip))
    if not ps: return None
    out = {}
    if chip in FACILITY_DESC: out['desc'] = clean(strings(15)[FACILITY_DESC[chip]])
    out['weight'] = ps[0][1][17]
    return out

# ---- aircraft -------------------------------------------------------------------------------------------------------------------------------------------
GEARS = ['GEAR', 'SEA', 'VTOL', 'HELI', 'UFO']
AIR_GROUPS = {28: 'FIGHTER', 29: 'INTERCEPT', 30: 'BOMBER', 31: 'SCOUT', 32: 'HELI', 33: 'SPECIAL'}
# aircraft weapon id (9000 + n) -> DAT 14 name string; ids 9000-9021 are consecutive from string 266, the bombs 9028-9032 from 288, the lasers by hand
WEAPON_NAME = dict([(9000 + k, 266 + k) for k in range(22)] + [(9022, 168), (9023, 169), (9025, 170), (9026, 171), (9027, 172)] + [(9028 + k, 288 + k) for k in range(5)])

def weapon_name(wid):
    k = WEAPON_NAME.get(wid)
    return clean(strings(14)[k]) if k is not None else 'weapon #%d' % wid

def aircraft_stats():
    """{(group name, chip index): dict(kind, gear, speed, range, endurance, night, heavy_weather, weapons, levels)} from DAT 6 array 0 (259 x 132 bytes = 3 strength levels
    of 44 bytes; the middle one is the aircraft as listed) and the chip pairs of DAT 32."""
    d32 = entry(32); pairs = [struct.unpack_from('<HH', d32, 4 * k) for k in range(len(d32) // 4)]
    b6 = entry(6); o0 = struct.unpack_from('<2I', b6, 12)[0]; out = {}
    for r in range(259):
        g, i = pairs[r + 1]
        if g not in AIR_GROUPS: continue
        lv = [struct.unpack_from('<22H', b6, o0 + 132 * r + 44 * k) for k in range(3)]; s = lv[1]
        ws = [(w, q) for w, q in zip((s[15], s[16]), s[18:20]) if w != 0xffff]
        out[(AIR_GROUPS[g], i)] = dict(kind='aircraft', gear=GEARS[(s[9] >> 8) & 7], speed=s[5], range=s[2], endurance=s[4], night=bool(s[10] & 1), heavy_weather=bool(s[10] & 0x100),
                                       weapons=[dict(name=weapon_name(w), rounds=q) for w, q in ws], levels=[dict(range=x[2], endurance=x[4], speed=x[5]) for x in lv])
    return out

