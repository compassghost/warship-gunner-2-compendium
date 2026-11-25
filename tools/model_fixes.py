"""Hand fixes for single models, shared by tools/export_models.py and tools/reexport_fixed.py.

INHERIT_ROOT: in these weapon models some nodes are flagged as roots although they have a different parent, so psc1.py leaves out the parent's offset and the part sits in the
wrong place (a turret sunk into its crate, a base off to the side of the turret). The flag appears on about 800 nodes in the game files, so it is NOT changed in psc1.py; for every
weapon dock (H) / in-game (L) pair, the models listed here are those for which treating those nodes as children makes the two files coincide again (distance between their bounding
boxes: Gatling w_ga_002 383 -> 5, Pulse Laser w_en_008 141 -> 3, w_tk_005 286 -> 2, w_ki_009 279 -> 2, w_ko_001 209 -> 9 ...; found 2026-11-14 after the user saw the Sil Laser,
Pulse Laser and Gatling Cannon dock models off). Only weapons were tested: the one other pair the rule changes (u_ca_kab_06) gets worse, so it is not listed."""
import psc1

_PAIRS = ['w_ko_001', 'w_ki_009', 'w_ga_002', 'w_gy_033', 'w_gy_035', 'w_ro_000', 'w_ms_005', 'w_ms_007', 'w_ms_003', 'w_en_008', 'w_tk_006', 'w_tk_005', 'w_en_006']
INHERIT_ROOT = {b + s for b in _PAIRS for s in ('H', 'L')}

def apply(model, parts):
    """Treat root-flagged nodes with another parent as children of that parent and bake the vertices again (in place)."""
    if model['name'] not in INHERIT_ROOT: return False
    for p in parts:
        for k, n in enumerate(p['nodes']):
            if n['root'] and n['parent'] != k: n['root'] = False
        p['verts'] = psc1.bake(model, p, 0)
    return True
