"""Compose the full item name of every tree chip the way the game does.
Chip field [3] + 34 indexes the full-name fragment table (project DAT entry 33). Field [14] indexes a template in the label table
(entry 34); template tokens: ~Ca1 = this chip's fragment, ~Ca0 = the group's generic fragment (entry 33 index = group number),
~Ip = the parent chip's fragment, ~Iw = the fragment of the nearest ancestor of kind 1 (the 'diameter' / 'level' chip).
A template without tokens is an explicit full name."""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(__file__))
import wg2, dat_tables as dt
ROOT = os.path.join(os.path.dirname(__file__), '..')

def load_entry(i):
    f = open(os.path.join(ROOT, 'iso_extract/DAT.BIN'), 'rb'); idx = wg2.read_index(f); o, s = idx[i]; f.seek(o)
    return dt.strings(wg2.decompress(f.read(s))[0])

ROMAN = {'Ⅰ': 'I', 'Ⅱ': 'II', 'Ⅲ': 'III', 'Ⅳ': 'IV', 'Ⅴ': 'V', 'Ⅵ': 'VI', 'Ⅶ': 'VII', 'Ⅷ': 'VIII', 'Ⅸ': 'IX', 'Ⅹ': 'X'}

def clean(s):
    s = re.sub(r'#[A-Za-z]\d*', '', s).replace('#=', '')
    return re.sub('[Ⅰ-Ⅹ]', lambda m: ROMAN[m.group(0)], s)   # plain-letter Roman numerals (serif-free on the web)

def compose():
    S33 = load_entry(33); S34 = load_entry(34)
    raw = json.load(open(os.path.join(ROOT, 'data/tree_raw.json')))
    chips = {(c['group'], c['index']): c for c in raw['chips']}
    frag = lambda c: S33[c['item_id'] + 34] if 0 <= c['item_id'] + 34 < len(S33) else ''
    def parent(c):
        anc = c['ancestors']
        if not anc: return None
        amap = {a: set(chips[(c['group'], a)]['ancestors']) for a in anc}
        direct = [a for a in anc if not any(a in amap[b] for b in anc if b != a)]
        return chips[(c['group'], direct[0])] if direct else None
    out = {}
    for key, c in chips.items():
        tpl = S34[c['raw_name_fields'][3]] if 0 <= c['raw_name_fields'][3] < len(S34) else '~Ca1'
        p = parent(c)
        iw = p
        while iw is not None and (iw['type'] != 1):
            iw = parent(iw)
        def sub(m):
            t = m.group(0)
            if t == '~Ca1': return frag(c)
            if t == '~Ca0': return S33[c['group']] if c['group'] < len(S33) else ''
            if t == '~Ip': return frag(p) if p else ''
            if t == '~Iw': return frag(iw) if iw else ''
            return t
        full = re.sub(r'~[A-Za-z]+\d*', sub, tpl)
        out[f"{c['group_name']}:{c['index']}"] = re.sub(r'\s+', ' ', clean(full)).strip()
    return out

if __name__ == '__main__':
    names = compose()
    json.dump(names, open(os.path.join(ROOT, 'data/full_names.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    print(len(names), 'names')
    for k in ['MAIN:0', 'MAIN:1', 'MAIN:2', 'MAIN:8', 'MAIN:10', 'MAIN:20', 'AMMO:1', 'AMMO:4', 'HULLS:1', 'HULLS:2', 'HULLS:7', 'BRIDGE:2', 'POWER:2', 'POWER:4', 'MACHINE:2', 'FIGHTER:1', 'FIGHTER:12', 'ATTACK:5', 'TORPEDO:1', 'TORPEDO:2', 'MISSILE:4']:
        print(k, '->', repr(names.get(k)))
