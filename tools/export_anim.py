"""Bake EVERY animation frame of every superweapon model that has more than one frame (BOS00-BOS15 and their parts) for web/boss_anim.html,
together with the game's own clip table. Output name stays web/models/anim_<id>.bin, the list is web/models/boss_anim.json.

web/models/anim_<id>.bin : u16 frames, u16 verts, u16 quads, u16 0; quads (u16 x4 each); uvs (u16 x8 each); then frames * verts * 3 float32.
web/models/lot_anim.json : per model the frame count and the CLIPS decoded from the model header (see below).

CLIP TABLE (decoded 2026-11-15, confirmed on all three models; layout of the header word at +0x18):
  a table of 8-byte pairs (u32 offset, u32 count), one pair per animation index (0 offset = unused); the pair table ends at header word +0x34.
  Each pair points to a list of 14-byte steps: u16 frame number, u16 duration (low 15 bits = ticks, bit 15 = LAST step of the clip), 10 zero bytes.
  So a clip is a stepped pose animation: show frame N for `duration` ticks, then the next step. A duration of 9999 on the last step means "hold".
  The pair's `count` is kept as `count` (its meaning is unknown; for the body dance it equals the clip's total ticks, 80).
  The tick rate is not known; the viewer assumes 60 ticks per second.
The pair index is the animation index the game code uses (object byte +0x3c / controller halfword +4, see notes/boss_health_table.md).
Run: python tools/export_anim.py"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import psc1, model_entities
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'web/models')
IDS = None                                   # None = every superweapon model that has more than one frame
# What each clip index is used for. The file has no names: these come from the user's memory of the game ("dance") or from reading the
# game code that sets the clip (notes/boss_health_table.md, "Hell Atsche" and "Supports"). Only confirmed uses are listed.
HA_BODY = {1: 'Closed / idle (hold)', 2: 'Open muzzle vanes (starts the beam phase)', 3: 'Hold open (lightning phase)', 4: 'Close vanes', 5: 'Return to rest'}
HA_SUPPORT = {1: 'Damaged (below half health)', 2: 'Destroyed (collapse)'}
LABELS = {('chr_1224', 2): 'Dance'}
LABELS.update({('chr_1198', k): v for k, v in HA_BODY.items()})
LABELS.update({('chr_1199', k): v for k, v in HA_SUPPORT.items()}); LABELS.update({('chr_1200', k): v for k, v in HA_SUPPORT.items()})

def read_clips(d):
    t = struct.unpack_from('<I', d, 0x18)[0]; end = struct.unpack_from('<I', d, 0x34)[0]
    clips = []
    for i in range((end - t) // 8):
        o, c = struct.unpack_from('<2I', d, t + 8 * i)
        if not o or not (0x48 <= o < t): continue
        steps = []; a = o
        while a + 14 <= t:
            fr, du = struct.unpack_from('<2H', d, a); a += 14
            steps.append([fr, du & 0x7fff])
            if du & 0x8000: break
        clips.append(dict(id=i, count=c, steps=steps, hold=steps[-1][1] >= 9999, label=''))
    return clips

def write_nodes(model, part, mid):
    """web/models/nodes_<id>.bin: the skeleton, so the page can blend between two frames per node (rotation, position, scale) instead of mixing vertices.
    u16 nodes, u16 frames, u16 verts, u16 0; u16 parent[nodes] (0xffff = root); u16 (first, end) vertex per node; pad to 4; float32 local vertices (verts x 3);
    then per frame, per node 7 float32: rotation x, y, z (65536 = full turn), position x, y, z (vertex units), scale. Same maths as psc1.node_transforms."""
    nodes = part['nodes']; nn = len(nodes); nf = model['frames']; ps = model['pos_scale']; nv = len(part['local_verts'])
    blob = bytearray(struct.pack('<4H', nn, nf, nv, 0))
    hp = psc1.hier_parents(part)
    blob += struct.pack('<%dH' % nn, *[0xffff if p is None else p for p in hp])
    blob += struct.pack('<%dH' % (2 * nn), *[min(c, 0xffff) for n in nodes for c in n['verts']])
    while len(blob) % 4: blob += b'\0'
    blob += struct.pack('<%df' % (3 * nv), *[float(c) for v in part['local_verts'] for c in v])
    for f in range(nf):
        for n in nodes:
            pi, ri = n['track'][min(f, len(n['track']) - 1)] if n['track'] else (0, 0xffff)
            p = model['pos'][pi] if pi < len(model['pos']) else (0, 0, 0, 1024)
            r = model['rot'][ri] if ri < len(model['rot']) else (0, 0, 0)
            blob += struct.pack('<7f', r[0], r[1], r[2], p[0] * ps, p[1] * ps, p[2] * ps, p[3] / 1024)
    open(os.path.join(OUT, 'nodes_%s.bin' % mid), 'wb').write(blob)

def main():
    idx = json.load(open(os.path.join(OUT, 'index.json'), encoding='utf8'))
    meta = []
    for base in [m for m in idx if m.get('cat') == 'superweapon']:
        mid = base['id']
        d = model_entities.Arc(base['archive']).get(base['entry'])
        model = psc1.parse_model(d)
        nf = model['frames']
        if IDS is not None and mid not in IDS or nf < 2: continue
        part = [p for p in model['parts'] if p['quads']][0]
        nv = len(psc1.bake(model, part, 0))
        blob = bytearray()
        blob += struct.pack('<4H', nf, nv, len(part['quads']), 0)
        blob += struct.pack('<%dH' % (4 * len(part['quads'])), *[c for q in part['quads'] for c in q])
        blob += struct.pack('<%dH' % (8 * len(part['uvs'])), *[c for u in part['uvs'] for c in u])
        for f in range(nf):
            V = psc1.bake(model, part, f, children=True)                  # hierarchy from the child lists, as the game walks it
            blob += struct.pack('<%df' % (3 * nv), *[c for v in V for c in v])
        open(os.path.join(OUT, 'anim_%s.bin' % mid), 'wb').write(blob)
        write_nodes(model, part, mid)
        clips = read_clips(d)
        for c in clips: c['label'] = LABELS.get((mid, c['id']), '')
        meta.append(dict(id=mid, name=base['name'], boss=base.get('cls') or '', frames=nf, verts=nv, quads=len(part['quads']), tex='models/%s.png' % mid, clips=clips))
        print(mid, nf, 'frames', nv, 'verts', len(blob), 'bytes', len(clips), 'clips')
    json.dump(meta, open(os.path.join(OUT, 'boss_anim.json'), 'w'), separators=(',', ':'))

if __name__ == '__main__':
    main()
