"""Model -> texture and model -> in-game entity links, read from the game's own tables (project DAT entry 3).

  array 2 (1,023 x 24 bytes) = model resource table: u16 model file id, u16 texture file id, u16, u16 flags. File ids are global
            (archive base + entry + 1, see notes/formats.md); the row number is the "resource index".
  array 3 (1,072 x 24 bytes) = entity class table: u16 resource index, 7 x u16 properties, u32, u32 -> name string (Shift-JIS / ASCII, may be 0).
            Several entities can share one resource (model), e.g. the four Duck aircraft all use resource 191 = O_FG_00.

Run: python tools/model_entities.py  -> data/model_entities.json (one row per PSC1 model in CHR / MDT_SHIP / MDT_WEPH / MDT_WEPL)."""
import os, sys, json, struct, re
sys.path.insert(0, os.path.dirname(__file__))
import wg2, dat_tables
ROOT = os.path.join(os.path.dirname(__file__), '..')
BASES = [(0, 'MAP'), (2000, 'CHR'), (4000, 'EFC'), (5000, 'PRV'), (6000, 'DAT'), (7000, 'SNDPS2'), (8000, 'BEV'), (11000, 'DSN'), (15000, 'EVT'),
         (18000, 'MDT_SHIP'), (19000, 'MDT_WEPH'), (21000, 'MDT_WEPL'), (24000, 'VCEPS2J')]
MODEL_ARCS = ('CHR', 'MDT_SHIP', 'MDT_WEPH', 'MDT_WEPL')

class Arc:
    def __init__(self, name):
        self.f = open(os.path.join(ROOT, 'iso_extract', name + '.BIN'), 'rb'); self.idx = wg2.read_index(self.f)
    def get(self, e):
        o, s = self.idx[e]; self.f.seek(o); return wg2.decompress(self.f.read(s))[0]

def file_ref(gid):
    """Global file id -> (archive, project entry) or None."""
    if gid == 0 or gid >= 30000: return None
    base, arc = max(b for b in BASES if b[0] < gid)
    return arc, gid - base - 1

def tables():
    d = Arc('DAT').get(3); A = dat_tables.arrays(d)
    res = []
    for k in range(A[2]['count']):
        m, t, c2, fl = struct.unpack_from('<4H', d, A[2]['offset'] + 24 * k)
        res.append(dict(index=k, model=file_ref(m), texture=file_ref(t), raw=(m, t, c2, fl)))
    ents = []
    for k in range(A[3]['count']):
        o = A[3]['offset'] + 24 * k
        rid = struct.unpack_from('<H', d, o)[0]; props = struct.unpack_from('<7H', d, o + 2); sp = struct.unpack_from('<I', d, o + 20)[0]
        name = d[sp:d.index(b'\0', sp)].decode('cp932', 'replace').strip() if 0 < sp < len(d) else ''
        name = JA.get(name, name)
        ents.append(dict(row=k, resource=rid, name=name, props=props))
    return res, ents

NATION = dict(J='Japan', E='Britain', G='Germany', U='USA', O='Other', A='Special')
AIR = dict(AK='Attack', BM='Bomber', FG='Fighter', HE='Helicopter', TE='Scout', VT='VTOL / special')
# Entity names the game table stores in Japanese -> English (ship names romanised, labels translated)
JA = {'大和': 'Yamato', '武蔵': 'Musashi', '金剛': 'Kongo', '摩耶': 'Maya', 'DDV たかまがはら': 'DDV Takamagahara', 'DDV くにつかぜ': 'DDV Kunitsukaze',
      'DDV よもつかぜ *ECM': 'DDV Yomotsukaze *ECM', '流氷': 'Drift ice', '名称未設定': 'Unnamed', 'ダミー艦': 'Dummy ship'}
SHIP = dict(DD='destroyer', CA='cruiser', BB='battleship', BC='battlecarrier', CB='large cruiser', CV='carrier', SS='submarine', GY='torpedo boat',
            YU='transport', AG='auxiliary / special', FF='frigate', BCV='battlecarrier')
PART = dict(sen='hull', kaa='forward bridge', kab='aft bridge', ent='funnel', elv='elevator', cat='aircraft catapult', tan='searchlight', hlp='helipad')
WEP = dict(ho='gun turret', ko='high-angle gun', ki='machine gun', ga='gatling / CIWS', gy='torpedo launcher', to='depth charge / thrower', ro='rocket launcher',
           ms='missile launcher', en='energy weapon', tk='special weapon')
EFFECT = dict(AWA='wake / foam effect', AMZ='muzzle flash effect', ABL='projectile', AEX='explosion effect', ASA='effect', AKO='effect', ALA='laser effect',
              AEC='effect', ADE='decoy', AAT='effect', ASH='effect', ATP='effect', AAP='effect', AKI='effect')

def describe(name):
    """Category from the model's internal name (inferred from the naming scheme, not from a game table)."""
    m = re.match(r'^([JEGUO])_(AK|BM|FG|HE|TE|VT)_(\d+)$', name)
    if m: return 'aircraft', '%s %s #%s' % (NATION[m.group(1)], AIR[m.group(2)], m.group(3))
    m = re.match(r'^([JEGUO])_(DD|CA|BB|BC|CB|CV|SS|GY|YU|AG)_(\d+)$', name)
    if m: return 'enemy ship', '%s %s #%s' % (NATION[m.group(1)], SHIP[m.group(2)], m.group(3))
    m = re.match(r'^([jeuga])_(dd|ca|bb|cv|bcv|ss|ff|ag)_(sen|kaa|kab|ent|elv|cat|tan|hlp)_?(\w*)$', name)
    if m: return 'player ship part', '%s %s %s %s' % (NATION[m.group(1).upper()], SHIP[m.group(2).upper()], PART[m.group(3)], m.group(4))
    m = re.match(r'^w_(ho|ko|ki|ga|gy|to|ro|ms|en|tk)_(\d+)', name)
    if m: return 'player weapon', '%s #%s' % (WEP[m.group(1)], m.group(2))
    m = re.match(r'^BOS(\d\d)([A-Z]?)$', name)
    if m: return 'superweapon', 'boss %s%s' % (m.group(1), (' variant / sub-unit ' + m.group(2)) if m.group(2) else '')
    m = re.match(r'^(?:BF|BOS)(\d\d)(\d)$', name)
    if m: return 'superweapon part', 'part %s of boss %s (BOS%s)' % (m.group(2), m.group(1), m.group(1))
    if name.startswith('BOF'): return 'superweapon part', 'shared boss part'
    if name.startswith('ITM'): return 'pickup item', 'floating item'
    if name.startswith('OBJ'): return 'map object', 'land / sea object'
    if name.startswith('DOCKJ') or name.startswith('DOBJ'): return 'dock scenery', 'port / dock scene object'
    for k, v in EFFECT.items():
        if name.startswith(k): return 'effect', v
    return 'other', ''

# The game text calls six auxiliary models "流氷" (drift ice). Checked in the viewer: these three are warships (the first two share Yomotsukaze's hull), the others really are ice.
NOT_ICE = {'J_AG_03', 'J_AG_04', 'E_AG_00'}
RENAME = {'BOS05A': ['Musspellheim (damaged)']}      # user-identified: chr_1160 is the damaged Musspellheim (the game text gives it the same name as BOS05)
BOSS_NAME = {}      # filled by build(): boss number -> first entity name of the main model BOSnn

# Class labels the internal name gets wrong (user, 2026-11-14): the "AG" (auxiliary / special) models that are really destroyer parts
CLS_OVERRIDE = {'j_ag_kaa_00H': 'Forward bridge - destroyer', 'j_ag_kaa_00L': 'Forward bridge - destroyer',      # Jpn DD FWD Bridge gamma
                'j_ag_sen_01H': 'Hull - destroyer', 'j_ag_sen_01L': 'Hull - destroyer'}                          # Jpn Destroyer 6
def klass(name, ents=()):
    """Class label inside a category, for sorting and grouping in the viewer (from the internal name; entities can override it)."""
    if name in CLS_OVERRIDE: return CLS_OVERRIDE[name]
    if any(e.startswith('YU ') for e in ents): return 'Transport'      # E_CV_07 "YU Collossus" / E_CV_08 "YU Transport" use carrier model names but are transports
    m = re.match(r'^([JEGUO])_(AK|BM|FG|HE|TE|VT)_(\d+)$', name)
    if m: return AIR[m.group(2)]
    m = re.match(r'^([JEGUO])_(DD|CA|BB|BC|CB|CV|SS|GY|YU|AG)_(\d+)$', name)
    if m: return SHIP[m.group(2)].capitalize()
    m = re.match(r'^([jeuga])_(dd|ca|bb|cv|bcv|ss|ff|ag)_(sen|kaa|kab|ent|elv|cat|tan|hlp)', name)
    if m: return '%s - %s' % (PART[m.group(3)].capitalize(), SHIP[m.group(2).upper()])
    m = re.match(r'^w_(ho|ko|ki|ga|gy|to|ro|ms|en|tk)_', name)
    if m: return WEP[m.group(1)].capitalize()
    m = re.match(r'^(?:BOS|BF)(\d\d)', name)
    if m: return BOSS_NAME.get(m.group(1), 'Boss ' + m.group(1))        # the boss's first game name, e.g. Boss 00 -> Wirbelwind (even for parts whose own names differ)
    for k, v in EFFECT.items():
        if name.startswith(k): return v.capitalize()
    return ''

def build():
    res, ents = tables(); arcs = {a: Arc(a) for a in MODEL_ARCS}
    by_model = {}
    for r in res:
        if r['model'] and r['model'][0] in MODEL_ARCS: by_model.setdefault(tuple(r['model']), []).append(r)
    names_by_res = {}
    for e in ents:
        if e['name']: names_by_res.setdefault(e['resource'], []).append(e['name'])
    out = []
    for a in MODEL_ARCS:
        A = arcs[a]
        kinds = []
        for e in range(len(A.idx)):
            try: d = A.get(e)
            except Exception: d = b''
            kinds.append(d[:6]);
            if d[:4] != b'PSC1': continue
            o = struct.unpack_from('<I', d, 0x3c)[0]; name = d[o:o + 16].split(b'\0')[0].decode('latin1') if o else ''
            rows = by_model.get((a, e), [])
            tex = None; src = None
            for r in rows:
                if r['texture'] and r['texture'][0] in MODEL_ARCS: tex = list(r['texture']); src = 'game table'; break
            ent_names = []
            for r in rows:
                for n in names_by_res.get(r['index'], []):
                    if n not in ent_names: ent_names.append(n)
            cat, desc = describe(name)
            if name in RENAME: ent_names = RENAME[name]
            if name in NOT_ICE and ent_names == ['Drift ice']: ent_names = ['Auxiliary ship (listed as "Drift ice")']
            if any(n.startswith('YU ') for n in ent_names): desc = desc.replace('carrier', 'transport')
            out.append(dict(id='%s_%d' % (a.lower(), e), archive=a, entry=e, name=name, category=cat, description=desc, resources=[r['index'] for r in rows],
                            texture=tex, texture_source=src, entities=ent_names))
        # models the resource table does not list: the low-detail twin of an MDT model uses the texture right after it
        for m in out:
            if m['archive'] != a or m['texture']: continue
            e = m['entry']
            if a != 'CHR' and e + 1 < len(kinds) and kinds[e + 1][:4] == b'SHTX': m['texture'] = [a, e + 1]; m['texture_source'] = 'next entry (not in the game table)'
    # Player hulls: the game table has no names for them. The number of hull models per nation and type equals the number of hull chips per
    # nation and type in the tech tree (145 in total), so hull NN is taken to be level NN+1. This is an inference from the counts, not a table link.
    nat = dict(j='Jpn', u='U.S.', e='U.K.', g='Ger'); typ = dict(dd='Destroyer', ca='Cruiser', bb='Battleship', cv='Carrier', bcv='Battlecarrier', ss='Submarine', ff='Frigate')
    special = dict(dd=['Small Destroyer', 'Twin-hull Destroyer', 'Mini Destroyer'], ca=['Twin-hull Cruiser', 'Special Cruiser'], cv=['Supercarrier'], bcv=['Gigantic Battlecarrier'],
                   ss=['Shark Submarine'], bb=['Drillship', 'Duckship', 'Small Battleship', 'Genuine Drillship', 'Twin-hull Battleship'])
    USER_BB = ['Drillship', 'Duckship', 'Small Battleship', 'Twin-hull Battleship', 'Genuine Drillship']     # a_bb_sen_00 .. 04
    for m in out:
        m['entities_inferred'] = []
        h = re.match(r'^([jeuga])_(dd|ca|bb|cv|bcv|ss|ff|ag)_sen_(\d+)[HL]$', m['name'])
        if not h: continue
        n, t, k = h.group(1), h.group(2), int(h.group(3))
        if t == 'ag': m['entities_inferred'] = ['Jpn Destroyer 6']
        elif n == 'a' and t == 'bb': m['entities'] = [USER_BB[k]]          # identified by the user in the viewer (2026-11-12), not the guide's order
        elif (n, t) == ('a', 'ca') and k in (0, 1):    # user-identified (2026-11-12): a_ca_sen_01 (544/546) is the Special Cruiser, a_ca_sen_00 the Twin-hull Cruiser
            m['entities'] = ['Twin-hull Cruiser' if k == 0 else 'Special Cruiser']
        elif n == 'a' and len(special.get(t, [])) == 1: m['entities_inferred'] = special[t]
        elif (n, t, k) == ('a', 'dd', 1): m['entities_inferred'] = ['Twin-hull Destroyer']     # twice as wide as the other two special destroyers (width 1506 vs 760)
        elif (n, t) == ('a', 'dd') and k in (0, 2):    # user-identified (2026-11-12): a_dd_sen_02 (length 6062) is the Mini Destroyer, a_dd_sen_00 (length 6432) the Small Destroyer
            m['entities'] = ['Small Destroyer' if k == 0 else 'Mini Destroyer']
        elif n == 'a': m['entities_inferred'] = ['one of: ' + ', '.join(special.get(t, []))]
        else: m['entities_inferred'] = ['%s %s %d' % (nat[n], typ[t], k + 1)]
    # Tech-tree chips: an entity whose name equals a chip's full name (data/full_names.json, ignoring spacing / punctuation) is that chip.
    try: full = json.load(open(os.path.join(ROOT, 'data/full_names.json'), encoding='utf8'))
    except Exception: full = {}
    ROMAN = 'ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ'
    def norm(s):
        for i, r in enumerate(ROMAN): s = s.replace(r, '<%d>' % (i + 1))
        return re.sub(r'[^a-z0-9<>]', '', s.lower())
    by = {}
    for k, v in full.items():
        if norm(v): by.setdefault(norm(v), []).append(k)
    for m in out:
        if m['entities']: keys = [norm(n) for n in m['entities']]
        else: keys = [norm(re.sub(r' (\d+)$', lambda g: ' <%s>' % g.group(1), n)) for n in m['entities_inferred'] if not n.startswith('one of')]   # hull level 3 = chip "... Ⅲ"
        m['chips'] = sorted({c for k in keys for c in by.get(k, [])})
    for m in out:
        b = re.match(r'^BOS(\d\d)$', m['name'])
        if m['archive'] == 'CHR' and b and m['entities']: BOSS_NAME[b.group(1)] = m['entities'][0]
    return out

if __name__ == '__main__':
    out = build()
    json.dump(out, open(os.path.join(ROOT, 'data/model_entities.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    # web/models/chips.json: tech-tree chip ("GROUP:index") -> model id, and normalised entity name -> model id, for the tree page's thumbnail viewer.
    # A name used by two models (Altair II is both a bomber and a fighter) goes to the model whose class matches the chip's tree.
    PREF = dict(FIGHTER='_AK_', INTERCEPT='_FG_', BOMBER='_BM_', SCOUT='_TE_', HELI='_HE_', SPECIAL='_VT_')
    cands = {}; names = {}
    for m in out:
        if m['archive'] != 'CHR' or m['category'] != 'aircraft': continue
        for c in m['chips']: cands.setdefault(c, []).append(m)
        for nme in m['entities']: names.setdefault(re.sub(r'[^a-z0-9]', '', nme.lower()), []).append(m['id'])
    if 'j7wshinden' in names: names['7wshinden'] = names['j7wshinden']        # the game's chip text drops the J
    chips = {}
    for c, ms in cands.items():
        want = PREF.get(c.split(':')[0], '')
        best = [m for m in ms if want and want in m['name']] or ms
        chips[c] = best[0]['id']
    # hulls: the dock (H) model of each player hull; the chip link is the inferred level/nation match (see above)
    for m in out:
        if m['archive'] == 'MDT_SHIP' and m['name'].endswith('H') and '_sen_' in m['name']:
            for c in m['chips']: chips.setdefault(c, m['id'])
            for nme in m['entities'] or m['entities_inferred']:
                if not nme.startswith('one of'): names.setdefault(re.sub(r'[^a-z0-9]', '', nme.lower()), []).append(m['id'])
    # weapons: hand-identified links in data/weapon_models.json (model file name -> chips whose full name matches a pattern)
    try:
        WL = json.load(open(os.path.join(ROOT, 'data/weapon_models.json'), encoding='utf8'))['links']
        fullnames = json.load(open(os.path.join(ROOT, 'data/full_names.json'), encoding='utf8'))
        byname = {m['name']: m['id'] for m in out if m['archive'] == 'MDT_WEPH'}
        wl = 0; labels = {}
        for l in WL:
            mid = byname.get(l['model'] + 'H')
            if not mid: print('weapon model not found:', l['model']); continue
            labels[mid] = l['label']
            for k, v in fullnames.items():
                if 'group' not in l: break
                if k.startswith(l['group'] + ':') and re.search(l['match'], v): chips[k] = mid; wl += 1
        json.dump(labels, open(os.path.join(ROOT, 'web/models/weapon_labels.json'), 'w', encoding='utf8'), indent=0, ensure_ascii=False)
        print(wl, 'weapon chips linked by hand;', len(labels), 'models labelled')
    except FileNotFoundError: pass
    # chips the user confirmed have no model at all (data/weapon_models.json "no_model"): the tree page does not flag them as "model missing"
    nomodel = []
    try:
        for l in json.load(open(os.path.join(ROOT, 'data/weapon_models.json'), encoding='utf8')).get('no_model', []):
            nomodel += [k for k, v in fullnames.items() if k.startswith(l['group'] + ':') and re.search(l['match'], v)]
    except FileNotFoundError: pass
    names['ukdestroyervi'] = ['mdt_ship_%d' % next(m['entry'] for m in out if m['name'] == 'e_dd_sen_05H')]       # the pickup-only hull
    os.makedirs(os.path.join(ROOT, 'web/models'), exist_ok=True)
    json.dump(dict(chips=chips, none=nomodel, names={k: v[0] for k, v in names.items() if len(set(v)) == 1}), open(os.path.join(ROOT, 'web/models/chips.json'), 'w', encoding='utf8'), separators=(',', ':'))
    print(len(chips), 'aircraft chips linked to a model;', sum(1 for c, ms in cands.items() if len(ms) > 1), 'resolved by class')
    n = len(out); print(n, 'models;', sum(1 for m in out if m['texture']), 'with a texture link;', sum(1 for m in out if m['entities']), 'with entity names;',
                        sum(1 for m in out if m['archive'] == 'CHR' and not m['resources']), 'CHR models not in the resource table')
