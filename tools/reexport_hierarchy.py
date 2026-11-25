"""Re-export the rest pose of every model whose geometry changes when the node hierarchy is taken from the child lists (psc1.hier_parents) instead of the
parent field + bit 15 (found 2026-11-15, see notes/boss_health_table.md). Rewrites only web/models/<id>.bin and the "size" of those entries in web/models/index.json;
textures, names, categories and every unchanged model are left alone.
Validation (2026-11-15): of 395 dock (H) / in-game (L) weapon model pairs the new rule brings 11 closer together (exactly the models hand-fixed in tools/model_fixes.py) and
makes none worse.
Run: python tools/reexport_hierarchy.py"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import psc1, model_entities
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/models')
idx_path = os.path.join(OUT, 'index.json')
index = json.load(open(idx_path, encoding='utf8'))
arcs = {}; changed = 0
for m in index:
    A = arcs.setdefault(m['archive'], model_entities.Arc(m['archive']))
    try: model = psc1.parse_model(A.get(m['entry']))
    except Exception: continue
    parts = [p for p in model['parts'] if p['quads']]
    if [(p['slot'], len(p['verts']), len(p['quads'])) for p in parts] != [(x['slot'], x['v'], x['q']) for x in m['parts']]: print('layout differs, skipped', m['id']); continue
    new = [psc1.bake(model, p, 0, children=True) for p in parts]; old = [psc1.bake(model, p, 0, children=False) for p in parts]
    if all(max((abs(a - b) for u, v in zip(n, o) for a, b in zip(u, v)), default=0) < 0.01 for n, o in zip(new, old)): continue
    blob = bytearray()
    for p, V in zip(parts, new):
        blob += struct.pack('<%df' % (3 * len(V)), *[c for v in V for c in v])
        blob += struct.pack('<%dH' % (4 * len(p['quads'])), *[c for q in p['quads'] for c in q])
        blob += struct.pack('<%dH' % (8 * len(p['uvs'])), *[c for u in p['uvs'] for c in u])
    open(os.path.join(OUT, m['id'] + '.bin'), 'wb').write(blob)
    m['size'] = [round(max(v[a] for v in new[0]) - min(v[a] for v in new[0])) for a in range(3)]
    changed += 1
json.dump(index, open(idx_path, 'w', encoding='utf8'), separators=(',', ':'), ensure_ascii=False)
print(changed, 'models re-exported')
