"""Export the light faces of the dock props (DOCKJ00-70) to web/models/<id>_L.bin + dock_lights.json.

Found 2026-11-16 (user: "the lighting ... cones"): in these PSC1 models mesh slot 12 holds the props' night geometry, and its faces carry a face flag with bit 0x100
(0x104, 0x105, 0x108, 0x109, 0x10c) - the floodlight cones, spotlight beams and glare cards - plus, in the lamp / truck models, ordinary faces (flag 0x8) that duplicate the body.
Faces with bit 0x100 also have a non-zero UV attribute 4th byte (128 / 136) where the body faces have 0 (the 'blend' byte of the UV record). This script writes only the flagged faces,
in the same layout as the composite parts (f32 vertices, u16 quad indices, u16 uvs), so the viewers can draw exactly the game's light faces additively instead of guessing from dark texels.
Run: python tools/export_dock_lights.py"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import psc1, model_entities as me
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/models')

if __name__ == '__main__':
    idx = json.load(open(os.path.join(OUT, 'index.json'), encoding='utf-8')); C = me.Arc('CHR'); info = {}
    for m in idx:
        if not m['name'].startswith('DOCKJ'): continue
        mod = psc1.parse_model(C.get(m['entry'])); blob = bytearray(); nv = nq = 0
        for p in mod['parts']:
            if p['slot'] != 12 or not p['quads']: continue
            ks = [k for k in range(len(p['quads'])) if p['face_flags'][k] & 0x100 and p['uv_index'][k] is not None]
            if not ks: continue
            used = sorted({i for k in ks for i in p['quads'][k]}); new = {v: j for j, v in enumerate(used)}
            blob += struct.pack('<%df' % (3 * len(used)), *[c for v in used for c in p['verts'][v]])
            blob += struct.pack('<%dH' % (4 * len(ks)), *[new[i] for k in ks for i in p['quads'][k]])
            blob += struct.pack('<%dH' % (8 * len(ks)), *[c for k in ks for c in p['uvs'][k]])
            nv += len(used); nq += len(ks)
        if nq:
            open(os.path.join(OUT, m['id'] + '_L.bin'), 'wb').write(blob); info[m['id']] = dict(name=m['name'], v=nv, q=nq)
    json.dump(info, open(os.path.join(OUT, 'dock_lights.json'), 'w'), separators=(',', ':'))
    print(len(info), 'models with light faces:', ', '.join('%s (%d)' % (v['name'], v['q']) for v in info.values()))
