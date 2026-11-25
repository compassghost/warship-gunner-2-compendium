"""Export a CHR model baked at another animation frame, as an extra viewer model next to the normal one.

web/models/<id>_<tag>.bin / .png and an entry <id>_<tag> in web/models/poses.json (same layout as an index.json entry; the texture is a copy).
Posed copies are NOT put in index.json, so they do not show up in the model viewer's list; only the fortress page reads poses.json.
Usage: python tools/export_pose.py chr_1198 open 6     (hell atsche with the six muzzle vanes fully open = frame 6)
       python tools/export_pose.py chr_1198 v90 6 90,0   (same, with the vane hinges forced to 90 and 0 degrees: a custom pose, not a game frame)
Frames are not a continuous animation: they are numbered poses (see notes/hell_atsche.md)."""
import os, sys, json, struct, shutil
sys.path.insert(0, os.path.dirname(__file__))
import psc1, model_entities
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/models')

FIRST = (8, 10, 12, 14, 16, 18)     # chr_1198: front panel of each of the six muzzle vanes (the rear panel is the next node)

def set_vanes(model, frame, a, b):
    """chr_1198 only: take the roll of each vane from `frame` and set the hinge angles to a (front panel) and b (rear panel) degrees."""
    part = [p for p in model['parts'] if p['quads']][0]
    for k in FIRST:
        for node, ang in ((part['nodes'][k], a), (part['nodes'][k + 1], b)):
            pi, ri = node['track'][frame]
            x, y, z = model['rot'][ri] if ri < len(model['rot']) else (0, 0, 0)
            sign = -1 if x < 0 else 1                                       # the arm at 180 degrees roll uses negative angles
            model['rot'].append((int(round(sign * ang * 65536 / 360)), y, z))
            node['track'][frame] = (pi, len(model['rot']) - 1)

def main(mid, tag, frame, vanes=None):
    idx = json.load(open(os.path.join(OUT, 'index.json'), encoding='utf8'))
    base = next(m for m in idx if m['id'] == mid)
    pp = os.path.join(OUT, 'poses.json'); poses = json.load(open(pp, encoding='utf8')) if os.path.exists(pp) else []
    arc, ent = base['archive'], base['entry']
    d = model_entities.Arc(arc).get(ent)
    model = psc1.parse_model(d)
    if vanes: set_vanes(model, frame, *vanes)
    blob = bytearray(); k = 0
    for p in [p for p in model['parts'] if p['quads']]:
        V = psc1.bake(model, p, frame)
        blob += struct.pack('<%df' % (3 * len(V)), *[c for v in V for c in v])
        blob += struct.pack('<%dH' % (4 * len(p['quads'])), *[c for q in p['quads'] for c in q])
        blob += struct.pack('<%dH' % (8 * len(p['uvs'])), *[c for u in p['uvs'] for c in u])
        k += 1
    new_id = '%s_%s' % (mid, tag)
    open(os.path.join(OUT, new_id + '.bin'), 'wb').write(blob)
    src_png = os.path.join(OUT, mid + '.png')
    if os.path.exists(src_png): shutil.copyfile(src_png, os.path.join(OUT, new_id + '.png'))
    ent_new = dict(base); ent_new['id'] = new_id; ent_new['name'] = base['name'] + '_' + tag; ent_new['desc'] = (base.get('desc') or '') + ' (pose: frame %d, %s)' % (frame, tag)
    poses = [m for m in poses if m['id'] != new_id] + [ent_new]       # kept out of index.json so the viewer's list does not fill up with copies
    json.dump(poses, open(pp, 'w', encoding='utf8'), separators=(',', ':'), ensure_ascii=False)
    print('wrote', new_id, len(blob), 'bytes;', k, 'parts')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), tuple(float(v) for v in sys.argv[4].split(',')) if len(sys.argv) > 4 else None)   # optional 4th argument "a,b": vane hinge angles
