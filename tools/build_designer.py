"""Data for web/designer.html, designer3d.html and designer_models.html (the ship design screen): designer.json, from the game's own data only.

Sources:
  DAT entry 26  530 designs x 2048 bytes: hull id at 0x1a, mount records from 0x20 (u32 part id, u16 x, z, y, w, 4 flag bytes), count at 0x660.
                Mount coordinates are integer cells of the hull grid: x along the ship, y across (centre line ~23), z = height level.
  DAT entry 7   part table; part family / label / chip from tools/designer_parts.py (the part -> chip link of the game's tables, see notes/tree_stats.md).
  DAT 8 / 9 / 10  hulls, systems, speed curve (tools/designer_stats.py); DAT 6 / 32 aircraft; DAT 14 / 15 names and descriptions.
  web/models    hull model per hull and weapon models per chip (index.json, chips.json from tools/export_models.py / tools/model_entities.py), data/weapon_models.json (hand-identified links).
Run order: decode_rd_tree.py, full_names.py, export_models.py (for the model links), then  python tools/build_designer.py      (WG2_OUT = output folder, default web/)"""
import os, sys, json, struct, re, collections
sys.path.insert(0, os.path.dirname(__file__))
import game_stats as gs, designer_parts as dp
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.environ.get('WG2_OUT') or os.path.join(ROOT, 'web')
BARREL_FAMILIES = ('main gun', 'hi-angle gun', 'machine gun', 'torpedo', 'proto gun', 'rapid fire')
GCODE = {'INTERCEPT': 'VF', 'FIGHTER': 'VA', 'BOMBER': 'VB', 'SCOUT': 'VQ'}      # tree group -> the chip badge of the aircraft list (VF interceptor, VA fighter, VB bomber, VQ scout; helicopters HS anti-sub / HC support / HA attack)

def chip_names():
    """{'GROUP:i': full name} of every chip of the tree (also those the game never places) and the set of placed chips"""
    raw = json.load(open(os.path.join(ROOT, 'data/tree_raw.json')))['chips']
    full = {k: gs.clean(v) for k, v in json.load(open(os.path.join(ROOT, 'data/full_names.json'), encoding='utf8')).items()}
    S34 = gs.strings(34)
    for c in raw:                                  # a chip whose composed name is empty keeps its own label (game label table, DAT 34)
        k = '%s:%d' % (c['group_name'], c['index'])
        if not full.get(k) and 0 <= c['raw_name_fields'][0] < len(S34) and 'N/A' not in S34[c['raw_name_fields'][0]]: full[k] = gs.clean(S34[c['raw_name_fields'][0]])      # (a few unplaced chips carry the game's own spreadsheet error 'A#N/A' as their name)
    placed = {'%s:%d' % (c['group_name'], c['index']) for c in raw if c['x'] is not None or c['index'] == 0}
    return full, placed

def heli_code(loadout):
    """helicopter badge from the loadout: container = support (HC), air/ship missile = attack (HA), depth charges + air/sub missile = anti-sub (HS)"""
    names = ' '.join(w['name'] for w in loadout)
    if 'Container' in names: return 'HC'
    return 'HA' if 'Air/Ship' in names else 'HS'

def aircraft_systems():
    """-> (aircraft list, system list) with names, groups, chips, from DAT 6 / 9 / 32 and the chip names"""
    full, placed = chip_names(); S14 = gs.strings(14); out = dict(systems=[], aircraft=[])
    b9 = gs.entry(9); SYSN = {30012: S14[393].strip(), 30013: S14[394].strip()}      # the two system records that name no chip (DAT 14 strings 393 / 394)
    SYSG = {30012: 'ENIGMA', 30013: 'DEFENSE'}                                                # ... and the tab they belong to (Enigmatech ids are 30xxx; the shield is a defense system)
    for i in range(len(b9) // 0x44):
        u = struct.unpack_from('<34H', b9, 0x44 * i); s = struct.unpack_from('<34h', b9, 0x44 * i)
        g, c = u[32], u[33]; grp = gs.GROUPS[g] if g < len(gs.GROUPS) else None; key = '%s:%d' % (grp, c) if grp else None
        out['systems'].append(dict(id=u[0], group=grp or SYSG.get(u[0]), chip=c if grp else 65535, name=full.get(key) if key else SYSN.get(u[0]), word2=u[2], mask=u[4], percents=list(s[11:30]),
                                   pk=0 if key in placed else 1))
    d32 = gs.entry(32); pairs = [struct.unpack_from('<HH', d32, 4 * k) for k in range(len(d32) // 4)]
    b6 = gs.entry(6); o0 = struct.unpack_from('<2I', b6, 12)[0]; stats = gs.aircraft_stats()
    for r in range(259):
        rec = b6[o0 + 132 * r:o0 + 132 * (r + 1)]; g, c = pairs[r + 1]; grp = gs.GROUPS[g] if g < len(gs.GROUPS) else None; key = '%s:%d' % (grp, c) if grp else None
        mid = struct.unpack_from('<22H', rec, 44); gear = mid[9] >> 8
        code = GCODE.get(grp)
        if grp == 'SPECIAL' and key in full: code = {'Interceptor': 'VF', 'Fighter': 'VA', 'Bomber': 'VB', 'Scout': 'VQ'}.get(full[key].split(' ')[-1])      # the duck aircraft are named after their role
        if grp == 'HELI' or gear == 3:
            st = stats.get((grp, c)); code = heli_code(st['weapons']) if st else 'HC'
        out['aircraft'].append(dict(r=r, group=grp, chip=c, name=full.get(key) if key else None, kind=mid[0] >> 8, gear=gear, mid=list(mid), code=code or '??', pk=0 if key in placed else 1))
    return out

def main():
    os.makedirs(OUT, exist_ok=True)
    R = gs.parts(); b = gs.entry(26)
    idx = {m['id']: m for m in json.load(open(os.path.join(ROOT, 'web/models/index.json'), encoding='utf-8'))}
    chips = json.load(open(os.path.join(ROOT, 'web/models/chips.json'), encoding='utf8'))['chips']
    P = {str(pid): dp.info(pid, u) for pid, u in R.items()}
    hull_stats = gs.hull_stats()
    hull_model = {}
    for m in idx.values():
        if m['cat'] == 'player ship part' and m['name'].endswith('H') and m['cls'].startswith('Hull'):
            for e in m['ents']: hull_model[e.lower()] = m['id']
    import designer_stats as DS, designer_vp as DV
    ST = DS.Stats(); TB = ST.T          # the game's own tables (decoded from the executable, see notes/designer_code.md)
    designs = []; parts = {}; hulls = {}
    def make_part(pid):
        p = P.get(str(pid), {}); rec = R.get(pid); ch = p.get('chips') or []
        mdl = next((chips.get(c) for c in ch if chips.get(c)), None); fam = p.get('family')
        if not mdl and fam in ('forward bridge', 'aft bridge', 'smokestack') and 10000 <= pid < 26000:
            # bridges / funnels: model name = <nation letter>_<type>_<kaa fwd | kab aft | ent funnel>_<level>H; id = base + nation x 1000 + type x 100 + level
            base = {'forward bridge': 10000, 'aft bridge': 15000, 'smokestack': 22000}[fam]
            if fam == 'smokestack': nat, ty, lv = (pid - 22000) // 1000, ((pid - 22000) % 1000) // 100, pid % 100
            else: nat, ty, lv = (pid - base) // 1000, ((pid - base) % 1000) // 100, pid % 100
            if 0 <= nat < 4:      # (other ids: the E-tech bridge 14000 etc. have no nation)
                nm = '%s_%s_%s_%02dH' % ('jueg'[nat], {0: 'dd', 1: 'ca', 2: 'bb', 3: 'cv', 5: 'ss'}.get(ty, '?'), {'forward bridge': 'kaa', 'aft bridge': 'kab', 'smokestack': 'ent'}[fam], lv)
                mdl = next((i for i, mm in idx.items() if mm['name'] == nm), None)
        # mount variants of the AA guns: the weapon list (data/weapon_models.json, hand-identified) names the model of each variant. Carriers use the C variants (1114-1120 machine guns, 1028-1041 hi-angle) = the side mounts.
        VAR = [(1107, 1113, 'w_ki_004H'), (1114, 1120, 'w_ki_008H'), (1125, 1128, 'w_ki_012H'), (1028, 1041, 'w_ko_001H')]
        for lo, hi_, nm_ in VAR:
            if lo <= pid <= hi_:
                alt = next((i for i, mm in idx.items() if mm['name'] == nm_), None)
                if alt: mdl = alt
        return dict(tc=(ch[0] if ch else None), label=p.get('label', str(pid)), family=p.get('family', '?'), weight=rec[17] if rec else None, wb=list(rec[17:21]) if rec and fam in BARREL_FAMILIES else None, model=mdl)     # u16[17..20] = weight for 1..4 barrels
    for k in range(530):
        x = b[k * 2048:(k + 1) * 2048]; hid = struct.unpack_from('<I', x, 0x1a)[0]; n = struct.unpack_from('<I', x, 0x660)[0]
        sysl = ST.systems(x)
        mounts = [list(struct.unpack_from('<I4H4B', x, 0x20 + 16 * i)) for i in range(n)]
        key = gs.hull_name(hid) or 'hull %d' % hid
        if hid not in hulls:
            w = hull_stats.get(key.lower())
            alt = re.sub(r' (\w+)$', lambda m_: ' %d' % (gs.ROMAN.index(m_.group(1)) + 1 if m_.group(1) in gs.ROMAN else 0), key)
            mdl = hull_model.get(key.lower()) or hull_model.get(alt.lower())
            hulls[hid] = dict(id=hid, name=key, mw=w and w[0], hw=w and w[1], en=w and w[2], ai=w and w[3], tr=w and w[4], ss=w and w[5], model=mdl)
        hx = hulls[hid].setdefault('xr', [999, -1])               # x range of every mount in every design on this hull: the hull model is centred on it (hull fit, see notes/designer.md)
        for m in mounts:
            hx[0] = min(hx[0], m[1]); hx[1] = max(hx[1], m[1])
        for m in mounts:
            if m[0] not in parts: parts[m[0]] = make_part(m[0])
        designs.append(dict(n=k, name=gs.UNI_ROMAN_SUB(x[1:0x1a].split(b'\0')[0].decode('cp932')), hull=hid, mounts=[m[:5] + [m[5], m[6], m[7], m[8]] for m in mounts],
                            sys=[i for i in struct.unpack_from('<10h', x, 0x664)], air=[[struct.unpack_from('<h', x, 0x67c + 4 * j)[0], x[0x67e + 4 * j], x[0x67f + 4 * j]] for j in range(7)],
                            armor=x[0x1e], x200=1 if x[0x67a] else 0, sysW=sum(struct.unpack_from('<H', r, 0x3c)[0] for r in sysl), sysSpd=sum(struct.unpack_from('<h', r, 0x16)[0] for r in sysl),
                            vp=struct.unpack_from('<h', x, 0x678)[0]))
    for k_, u_ in TB.parts.items():      # every part of the game (the weapons picker needs all weapons, not only the ones the stock designs use)
        if k_ not in parts and str(k_) in P: parts[k_] = make_part(k_)
    # footprints of the engine parts from the game's own designs: the closest spacing of two identical parts along x (same y) and along y (same x) = the box they occupy
    sp = collections.defaultdict(lambda: [99, 99])
    for d_ in designs:
        ms = d_['mounts']
        for i, a in enumerate(ms):
            for b_ in ms[i + 1:]:
                if a[0] != b_[0] or a[4] != b_[4]: continue
                dx, dy = abs(a[1] - b_[1]), abs(a[3] - b_[3])
                if dy == 0 and dx > 0: sp[a[0]][0] = min(sp[a[0]][0], dx)
                if dx == 0 and dy > 0: sp[a[0]][1] = min(sp[a[0]][1], dy)
    for k, v in sp.items():
        if parts[k]['family'] in ('boiler', 'engine part'): parts[k]['fp'] = [v[0] if v[0] < 99 else (v[1] if v[1] < 99 else 6), v[1] if v[1] < 99 else (v[0] if v[0] < 99 else 6)]
    # the game's own numbers (DAT 7 / 8 / 10, decoded in notes/designer_code.md): part pictures, magazine shapes, weights, engine output, hull weight limit / weight / length
    _h7 = DV._dat(7); _ri = {}
    for i_ in range(1120): _ri.setdefault(struct.unpack_from('<H', _h7, 144 * i_)[0], i_)      # the game's part lookup walks the DAT 7 rows in order (the evaluation keeps the lowest row per weapon slot)
    for k, v in parts.items():
        u = TB.parts.get(k)
        if u: v.update(tb=u[67], ri=_ri.get(k, 0), cmd=u[35], rad=u[41], son=u[42], prg=u[34], isl=u[43], pic=list(u[7:13]), mag=list(u[13:17]), wb4=list(u[17:23]), kind=u[3] & 255, b4=u[2] & 255, zone=u[5] >> 8, hcls=u[5] & 255, flags=u[6], out=u[32], eff=u[33], dmg=u[32], rld=u[56], rds=u[55], dsp=u[57], rng=u[58], vital=1 if DV.is_vital(TB, k) else 0)
    if 700 in hulls: hulls[700]['name'] = 'Jpn Frigate I'      # the game's own design screen names hull 700 (the Japanese SDF Ship blueprint, 6000 t, hull weight 1150) "Jpn Frigate I" with the DD tag (observed in game, 2026-11-18)
    # the three bridges the id formula above cannot name: Jpn DD FWD / AFT Bridge gamma (10400 / 15300) = the "Japan auxiliary / special" bridge pair j_ag_kaa_00H / j_ag_kab_00H,
    # and the E-tech BB FWD Bridge (14000, no nation) = a_bb_kaa_00H "Special battleship forward bridge" (the only model of the 'a' special-ship set with a bridge; there is no aft one)
    for pid_, nm_ in ((10400, 'j_ag_kaa_00H'), (15300, 'j_ag_kab_00H'), (14000, 'a_bb_kaa_00H'), (19200, 'j_bb_tan_00H'), (19202, 'j_bb_tan_00H'), (19204, 'j_bb_tan_02H'), (19203, 'a_cv_tan_00H')):
        if pid_ in parts: parts[pid_]['model'] = next((i for i, mm in idx.items() if mm['name'] == nm_), None)
    if 19000 in parts: parts[19000]['model'] = None      # the non-side elevator has no model (the chip link gave it the side elevator's model j_cv_elv_00); the side elevator 19001 keeps it
    # models by barrel count (data/weapon_models.json, hand-identified: e.g. 46cm gun w_ho_130 / 133 / 136 / 139 = 1 / 2 / 3 / 4 barrels): the chip table gives only the 1-barrel model
    try: LINKS = json.load(open(os.path.join(ROOT, 'data/weapon_models.json'), encoding='utf8'))['links']      # optional: hand-identified links, absent in a fresh checkout
    except OSError: LINKS = []
    GROUP = {'main gun': 'MAIN', 'torpedo': 'TORPEDO', 'proto gun': 'PROTO'}
    nm2id = {mm['name']: i for i, mm in idx.items() if mm['archive'] == 'MDT_WEPH'}
    def barrel_model(fam, label, b):
        base = re.sub(r' \(mount variant \w\)', '', re.sub(r' \d+Cal', '', label)); cands = ([base + ' %dbrls' % b] if b > 1 else []) + [base]
        for cand in cands:
            for l in LINKS:
                if l.get('group') == GROUP[fam] and l.get('match') and re.search(l['match'], cand): return nm2id.get(l['model'] + 'H')
        return None
    for k, v in parts.items():
        if v['family'] in GROUP:
            bm = [barrel_model(v['family'], v['label'], b) for b in range(1, 7)]
            if v['family'] == 'main gun' and re.match(r'^12\.7cm Gun( \d+Cal)?( \(mount variant \w\))?$', v['label']): bm[1], bm[2] = nm2id.get('w_ho_008H'), nm2id.get('w_ho_015H')      # 12.7cm 2 / 3 barrels: their links have no 'match', so the 1-barrel model was used for all
            if any(bm): v['bm'] = [x or v['model'] for x in bm]
    for hid_, h in hulls.items():
        if hid_ in TB.hulls:
            u, L = TB.hulls[hid_]; h.update(slots=u[16] & 255, air=u[15] & 255, tr=u[15] >> 8, mwg=u[6] | (u[7] << 16), hwg=u[8], L=L, row=list(TB.hulls).index(hid_), pic=u[5] & 255, hclass=u[2] >> 8)      # picture = hull record u16[5] & 255 (notes/designer_code.md 9.1)
    # system records (DAT 9, 0x44 bytes, notes/designer_code.md 11.6): id, weight [0x3c], five stats [0xc..0x14] (endurance, radar, sonar, steering, command), 13 percent effects [0x16..]
    systems = {}
    for sid, rec in ST.sys.items():
        systems[str(sid)] = dict(w=struct.unpack_from('<H', rec, 0x3c)[0], st=list(struct.unpack_from('<5h', rec, 0xc)), ef=list(struct.unpack_from('<13h', rec, 0x16)), acl=rec[0x35], vis=rec[0x3b] & 7)      # acl = extra auto-fire level (Auto Countermeasures), vis = vision / positioning flag: both read by the evaluation (tools/designer_rank.py)
    AS = aircraft_systems(); S15 = gs.strings(15); b9 = gs.entry(9)
    for s_ in AS['systems']:
        tcs = (s_['group'] + ':' + str(s_['chip'])) if s_['group'] and s_['chip'] != 65535 and not s_['pk'] else None      # tech tree deep link; pick-up-only systems are not on the tree
        if str(s_['id']) in systems: systems[str(s_['id'])].update(tc=tcs, pk=s_['pk'], name=s_['name'] or 'System %d (unnamed)' % s_['id'], group=s_['group'] or 'OTHER', mask=s_['mask'], pc=s_['percents'])
    for i in range(len(b9) // 0x44):          # the game's own description of each system (DAT 15 string 1187 + (u16[31] & 255))
        u = struct.unpack_from('<34H', b9, 0x44 * i); s_ = systems.get(str(u[0]))
        d = 1187 + (u[31] & 255)
        if s_ is not None and 0 <= d < len(S15) and S15[d].startswith('#Y4#='): s_['desc'] = gs.clean(S15[d])
    for a_ in AS['aircraft']:
        if a_.get('name') == 'walrus': a_['name'] = 'Walrus'      # the interceptor tech tree entry is spelled in lower case in the game's own text (INTERCEPT:56)
        if a_['r'] == 241: a_['name'] = 'RAH-66 Comanche'      # the game's own list shows the full name (observed in game); its chip label is the placeholder 'A#N/A'
        if a_['r'] in (0, 1, 2): a_['name'] = 'Duck aircraft %d' % (a_['r'] + 1)      # the three identical placeholder records (180 range, 120 endurance, speed 2100)
    aircraft = [dict(tc=(a['group'] + ':' + str(a['chip']) if a['group'] and a['chip'] != 65535 else None), code=a['code'], pk=a['pk'], r=a['r'], name=a['name'] or 'Aircraft %d (unnamed)' % a['r'], group=a['group'] or 'OTHER', gear=a['gear'], kind=a['kind']) for a in AS['aircraft']]
    # speed / range / endurance of every record (the middle strength level of the DAT 6 record: u16[5], [2], [4])
    for a, a_ in zip(aircraft, AS['aircraft']):
        mid_ = a_.get('mid') or []
        # u16[10]: low byte = night mission, high byte = heavy weather (0 / 1; 257 = both)
        if len(mid_) > 10: a['st'] = [mid_[5], mid_[2], mid_[4], mid_[10] & 1, (mid_[10] >> 8) & 1]
    # the aircraft model by name: the model index lists the entity names that use each model (J_AK_06 = "J7W Shinden", E_VT_01 = "Viking FA2", ...); chips.json has no entry for these records
    ents = {}
    for mm in idx.values():
        if mm.get('cat') == 'aircraft' and mm['id'].startswith('chr_'):
            for e_ in mm.get('ents') or []: ents.setdefault(e_.lower(), []).append(mm['id'])
    for a in aircraft:
        if chips.get(a['tc'] or '') or not a['name']: continue
        n = a['name'].lower(); hit = ents.get(n) or []
        if not hit:
            cand = {i for e_, ids in ents.items() if e_.startswith(n + ' ') or e_.startswith(n + '-') or n.startswith(e_ + ' ') for i in ids}
            if len(cand) == 1: hit = list(cand)
        if len(hit) >= 1: a['model'] = hit[0]      # everything the game has, also the records without a research chip
    out = dict(aircraft=aircraft, systems=systems, designs=designs, parts={str(k): v for k, v in parts.items()}, hulls={str(k): v for k, v in hulls.items()},
               plating=[a[2] for a in TB.armor[:17]], armorSize=[0, 10, 12, 14, 15, 20, 25, 31, 36, 38, 41, 43, 46, 51, 56, 61, 80], curve=list(TB.curve))
    json.dump(out, open(os.path.join(OUT, 'designer.json'), 'w', encoding='utf8'), separators=(',', ':'), ensure_ascii=False)
    print(len(designs), 'designs', len(parts), 'parts', len(hulls), 'hulls;', 'no model:', [h['name'] for h in hulls.values() if not h['model']], 'no stats:', [h['name'] for h in hulls.values() if h['mw'] is None])

if __name__ == '__main__':
    main()


