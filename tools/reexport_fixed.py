"""Re-export only the models listed in tools/model_fixes.py (INHERIT_ROOT), without running the whole of export_models.py: rewrites their web/models/<id>.bin and the "size" of
their entries in web/models/index.json. Textures, names and every other model are left as they are.
Run: python tools/reexport_fixed.py"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import psc1, model_entities, model_fixes
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/models')
idx_path = os.path.join(OUT, 'index.json')
index = json.load(open(idx_path, encoding='utf8'))
by_id = {m['id']: m for m in index}
done = 0
for arc in ('MDT_WEPH', 'MDT_WEPL'):
    A = model_entities.Arc(arc)
    for e in range(len(A.idx)):
        try: d = A.get(e)
        except Exception: continue
        if d[:4] != b'PSC1': continue
        try: model = psc1.parse_model(d)
        except Exception: continue
        if model['name'] not in model_fixes.INHERIT_ROOT: continue
        mid = '%s_%d' % (arc.lower(), e)
        if mid not in by_id: print('not in index:', mid, model['name']); continue
        parts = [p for p in model['parts'] if p['quads']]
        model_fixes.apply(model, parts)
        meta = by_id[mid]['parts']
        assert [(p['slot'], len(p['verts']), len(p['quads'])) for p in parts] == [(m['slot'], m['v'], m['q']) for m in meta], 'part layout changed for ' + mid
        blob = bytearray()
        for p in parts:
            blob += struct.pack('<%df' % (3 * len(p['verts'])), *[c for v in p['verts'] for c in v])
            blob += struct.pack('<%dH' % (4 * len(p['quads'])), *[c for q in p['quads'] for c in q])
            blob += struct.pack('<%dH' % (8 * len(p['uvs'])), *[c for u in p['uvs'] for c in u])
        open(os.path.join(OUT, mid + '.bin'), 'wb').write(blob)
        V = parts[0]['verts']; by_id[mid]['size'] = [round(max(v[a] for v in V) - min(v[a] for v in V)) for a in range(3)]
        done += 1; print(mid, model['name'], 'size', by_id[mid]['size'])
json.dump(index, open(idx_path, 'w', encoding='utf8'), separators=(',', ':'), ensure_ascii=False)
print(done, 'of', len(model_fixes.INHERIT_ROOT), 'models re-exported')
