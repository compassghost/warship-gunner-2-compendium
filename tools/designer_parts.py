"""Part family / label / chip for every record of the part table (DAT 7), from the game's own data.
Order of evidence for a part:
  1. ids 0-265 (main guns) and 1000-1041 (hi-angle guns) are grids: diameter x cal-length x mount variant. The diameters are the 'diameter' chips (kind 1) of the MAIN / HI ANGLE
     tree groups (largest first); cal-lengths are 45, 50 ... 75; block A = ids 0-146 (21 diameters x 7), B = 147-181, C = 182-230, D = 231-265 (mount variants of the same guns);
     hi-angle: 12.7 cm then 10.0 cm, 7 cal-lengths each, three mount variants of 14 ids. (The game links these parts to the nearest *chip*, which for most grid points is another
     diameter, so the link is not used for them.)
  2. ids >= 8000 are enemy / aircraft weapons: family 'unknown', no label.
  3. every other part names its chip (u16[30] group, u16[31] chip, see game_stats.py): family from the group, label from the chip's full name.
  4. smokestacks, bridges and engines also get structural labels from their ids (nation x 1000 + class x 100 + level).
Needs data/tree_raw.json and data/full_names.json (tools/decode_rd_tree.py, tools/full_names.py)."""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(__file__))
import game_stats as gs
ROOT = os.path.join(os.path.dirname(__file__), '..')
FAMILY = {'MAIN': 'main gun', 'HI ANGLE': 'hi-angle gun', 'MACHINE': 'machine gun', 'RAPID': 'rapid fire', 'PROTO': 'proto gun', 'TORPEDO': 'torpedo', 'EXPLOSIVE': 'explosive',
          'MISSILE': 'missile', 'ROCKET': 'rocket', 'FLARE': 'flare', 'ORGANIC': 'organic', 'OPTICAL': 'optical', 'PLASMA': 'plasma', 'MAGNETIC': 'magnetic', 'PULSE': 'pulse',
          'A-MATTER': 'a-matter', 'BRIDGE': 'forward bridge', 'AFT': 'aft bridge', 'PURGE': 'smokestack', 'FACILITY': 'facility', 'POWER': 'boiler', 'ROTATION': 'engine part'}
BLOCKS = [(0, 'A'), (147, 'B'), (182, 'C'), (231, 'D')]
NAT = ['Jpn', 'U.S.', 'U.K.', 'Ger']
_ctx = {}

def ctx():
    if not _ctx:
        raw = json.load(open(os.path.join(ROOT, 'data/tree_raw.json')))['chips']
        full = {k: gs.clean(v) for k, v in json.load(open(os.path.join(ROOT, 'data/full_names.json'), encoding='utf8')).items()}
        def diameters(group, pat):
            ds = set()
            for c in raw:
                if c['group_name'] == group and c['type'] == 1:
                    m = re.match(pat, full.get('%s:%d' % (group, c['index']), ''))
                    if m: ds.add(float(m.group(1)))
            return sorted(ds, reverse=True)
        _ctx.update(full=full, main=diameters('MAIN', r'^(\d+\.\d)cm Gun'), hi=diameters('HI ANGLE', r'^(\d+\.\d)cm High Angle Gun'))
    return _ctx

def chip_for(group, base, cal):
    """tree chip of a gun: the exact cal-length chip when the tree has one, else the diameter's 45Cal chip"""
    inv = {v: k for k, v in ctx()['full'].items() if k.startswith(group + ':')}
    return inv.get('%s %dCal' % (base, cal)) or inv.get('%s 45Cal' % base)

def grid_main(pid):
    """block letter, diameter, cal-length for main gun ids 0-265, or None"""
    D = ctx()['main']
    if not 0 <= pid <= 265 or not D: return None
    for start, letter in reversed(BLOCKS):
        if pid >= start:
            k = pid - start
            ds = D if letter == 'A' else {'B': D[16:], 'C': D[14:], 'D': D[16:]}[letter]       # B and D: 15.5 .. 10.0; C: 25.4 .. 10.0 (the last 5 / 7 diameters)
            return letter, ds[k // 7], 45 + 5 * (k % 7)

def info(pid, u):
    """-> dict(family, label, group, chips) for part id pid with record u (u16[72])"""
    C = ctx(); link = None
    if u[30] < len(gs.GROUPS) and u[31] not in (0, 0xffff): link = '%s:%d' % (gs.GROUPS[u[30]], u[31])
    if 8000 <= pid < 10000: return dict(family='unknown', label='', group=None, chips=[])
    g = grid_main(pid)
    if g:
        letter, d, cal = g
        return dict(family='main gun', label='%.1fcm Gun %dCal%s' % (d, cal, '' if letter == 'A' else ' (mount variant %s)' % letter), group='MAIN', chips=[c for c in [chip_for('MAIN', '%.1fcm Gun' % d, cal)] if c])
    if 1000 <= pid <= 1041 and C['hi']:
        k = (pid - 1000) % 14
        return dict(family='hi-angle gun', label='%.1fcm High Angle Gun %dCal' % (C['hi'][k // 7], 45 + 5 * (k % 7)), group='HI ANGLE', chips=[c for c in [chip_for('HI ANGLE', '%.1fcm High Angle Gun' % C['hi'][k // 7], 45 + 5 * (k % 7))] if c])
    if 22000 <= pid < 26000:
        n, c, lv = (pid - 22000) // 1000, ((pid - 22000) % 1000) // 100, pid % 100
        return dict(family='smokestack', label='%s %s smokestack level %d' % (NAT[n], ('DD', 'CA', 'BB')[c] if c < 3 else '?', lv + 1), group='PURGE', chips=[link] if link else [])
    if link:
        grp = gs.GROUPS[u[30]]; fam = FAMILY.get(grp)
        label = C['full'].get(link, '')
        if grp == 'POWER': fam = 'boiler' if (u[3] & 255) == 20 else 'engine part'; label = '%s (generic, not modelled)' % fam
        if grp == 'ROTATION': label = 'engine part (generic, not modelled)'
        if fam == 'machine gun' and 'CIWS' in label: fam = 'CIWS'
        if grp == 'FACILITY': label = label.lower(); rank = [p for p, _ in gs.parts_by_chip()[(grp, u[31])]].index(pid); label = {('elevator', 1): 'side elevator', ('launcher', 1): 'small launcher', ('launcher', 2): 'small launcher'}.get((label, rank), label)
        if grp == 'MACHINE' and pid >= 1129: label += ' (mount variant D)'
        if fam: return dict(family=fam, label=label, group=grp, chips=[link])
    if (u[3] & 255) == 16: return dict(family='facility', label='searchlight (weight %d)' % u[17], group='FACILITY', chips=[])      # kind 16 = searchlight: the tree has no chip for it
    return dict(family='unknown', label='', group=None, chips=[])

