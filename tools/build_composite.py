"""Build the assembled boss models for the viewer ("Hell Atsche (Composite)", "Habakkuk (Composite)") from the exported single models.

Each data/composite_*.json describes one assembled boss as a list of parts; a part is a list of pieces (one part of one exported model, with an optional
position x y z, rotation yaw / pitch / roll in degrees and scale), or an 'arc' generator that repeats a piece around a circle. All pieces of a part are
merged into one mesh and share the texture of the model named in the part's "texid".
Writes web/models/composite_<name>.bin (same binary layout as every other model: per part Float32 xyz, Uint16 quads, Uint16 uvs) and all the entries into
web/models/composites.json. The viewer and the campaign page merge composites.json into their model list (kept apart from index.json, which
tools/export_models.py rewrites). Each entry has "all": true (draw every part together) and "boss" (the superweapon it replaces on the campaign page).
Run: python tools/build_composite.py   (after export_models.py and export_pose.py chr_1198 v45 6 45,0)"""
import os, json, math, struct, glob
ROOT = os.path.join(os.path.dirname(__file__), '..')
MODELS = os.path.join(ROOT, 'web/models')

_meta = {}
def meta_of(mid):
    if not _meta:
        for fn in ('index.json', 'poses.json'):
            for m in json.load(open(os.path.join(MODELS, fn), encoding='utf8')): _meta[m['id']] = m
    return _meta[mid]

def read_part(mid, k):
    """vertices [(x,y,z)], quads [(a,b,c,e)], uvs [8 values] of part k of an exported model"""
    m = meta_of(mid); d = open(os.path.join(MODELS, mid + '.bin'), 'rb').read(); off = 0
    for j in range(k): off += m['parts'][j]['v'] * 12 + m['parts'][j]['q'] * 24
    p = m['parts'][k]; nv, nq = p['v'], p['q']
    V = [struct.unpack_from('<3f', d, off + 12 * i) for i in range(nv)]
    qo = off + nv * 12; Q = [struct.unpack_from('<4H', d, qo + 8 * i) for i in range(nq)]
    uo = qo + nq * 8; U = [struct.unpack_from('<8H', d, uo + 16 * i) for i in range(nq)]
    return V, Q, U

def rot_euler_xyz(px, py, pz):
    """matrix of three.js Euler 'XYZ' (applied to a vector as Rz first, then Ry, then Rx); angles in radians"""
    cx, sx, cy, sy, cz, sz = math.cos(px), math.sin(px), math.cos(py), math.sin(py), math.cos(pz), math.sin(pz)
    Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]; Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]; Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    mul = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(Rx, Ry), Rz)

def place(V, R, t, s=1.0):
    return [tuple(s * (R[i][0] * v[0] + R[i][1] * v[1] + R[i][2] * v[2]) + t[i] for i in range(3)) for v in V]

class Part:
    def __init__(self): self.V, self.Q, self.U = [], [], []
    def add(self, V, Q, U):
        b = len(self.V); self.V += V; self.Q += [tuple(i + b for i in q) for q in Q]; self.U += U
    def blob(self):
        assert len(self.V) < 65536, 'too many vertices for 16-bit indices'
        return (struct.pack('<%df' % (3 * len(self.V)), *[c for v in self.V for c in v]) + struct.pack('<%dH' % (4 * len(self.Q)), *[c for q in self.Q for c in q])
                + struct.pack('<%dH' % (8 * len(self.U)), *[c for u in self.U for c in u]))

def add_piece(part, pc):
    V, Q, U = read_part(pc['model'], pc.get('part', 0))
    g = lambda k, d=0: pc.get(k, d)
    for ps in pc.get('pose', []):      # turn some of the model's nodes (vertex index ranges) about a pivot, in order: {"verts": [a, b], "axis": "x"|"y"|"z", "deg": d, "pivot": [x, y, z]}
        a, b = ps['verts']; ax = 'xyz'.index(ps['axis']); th = math.radians(ps['deg']); c, s = math.cos(th), math.sin(th); i, j = [(1, 2), (2, 0), (0, 1)][ax]; px = ps['pivot']
        for n in range(a, b):
            v = list(V[n]); p, q = v[i] - px[i], v[j] - px[j]; v[i], v[j] = px[i] + p * c - q * s, px[j] + p * s + q * c; V[n] = tuple(v)
    if 'verts' in pc:      # keep only the faces whose vertices all lie in these index ranges [[a, b), ...] (one node, or several, of the model); the rest is dropped and the indices renumbered
        keep = sorted({n for a, b in pc['verts'] for n in range(a, min(b, len(V)))}); new = {n: k for k, n in enumerate(keep)}
        sel = [k for k, q in enumerate(Q) if all(i in new for i in q)]
        V, Q, U = [V[n] for n in keep], [tuple(new[i] for i in Q[k]) for k in sel], [U[k] for k in sel]
    if pc.get('generator') == 'arc':
        rows = math.ceil(pc['count'] / pc['cols'])
        for i in range(pc['count']):
            c, r = i % pc['cols'], i // pc['cols']; zz = pc['z'] + (r - (rows - 1) / 2) * pc['dz']
            th = math.radians(pc['heading'] + ((c / (pc['cols'] - 1) - 0.5) * pc['arc'] if pc['cols'] > 1 else 0))
            R = rot_euler_xyz(math.radians(g('pitch')), math.radians(g('roll')), th + math.radians(90 + g('yaw')))
            part.add(place(V, R, (g('x') + pc['radius'] * math.sin(th), g('y') - pc['radius'] * math.cos(th), zz), g('scale', 1)), Q, U)
    elif pc.get('about') == 'centroid':       # turn the piece about its own centre (x, y, z then move it by that much)
        cx = sum(v[0] for v in V) / len(V); cy = sum(v[1] for v in V) / len(V)
        part.add(place([(v[0] - cx, v[1] - cy, v[2]) for v in V], rot_euler_xyz(math.radians(g('pitch')), math.radians(g('roll')), math.radians(g('yaw'))), (cx + g('x'), cy + g('y'), g('z')), g('scale', 1)), Q, U)
    else:
        part.add(place(V, rot_euler_xyz(math.radians(g('pitch')), math.radians(g('roll')), math.radians(g('yaw'))), (g('x'), g('y'), g('z')), g('scale', 1)), Q, U)

def build(cfg):
    parts = []
    for pd in cfg['parts']:
        p = Part()
        for pc in pd['pieces']: add_piece(p, pc)
        parts.append((p, pd))
    open(os.path.join(MODELS, cfg['id'] + '.bin'), 'wb').write(b''.join(p.blob() for p, _ in parts))
    base = meta_of(parts[0][1]['texid'])
    xs = [v[0] for p, _ in parts for v in p.V]; ys = [v[1] for p, _ in parts for v in p.V]; zs = [v[2] for p, _ in parts for v in p.V]
    entry = dict(id=cfg['id'], archive='COMPOSITE', entry=0, name=cfg['name'], variant='', cat='composite', cls='', desc=cfg.get('desc', ''), ents=[cfg['name']], inferred=False, all=True, boss=cfg['boss'], waterZ=cfg.get('water_z', 0),      # waterZ: height of the sea in model units (0 = the model's own zero)

                 parts=[dict(slot=k, v=len(p.V), q=len(p.Q), kind='mesh', untex=0, nodes=0, texid=pd['texid'], label=pd['label'], **({'anim': pd['anim']} if 'anim' in pd else {})) for k, (p, pd) in enumerate(parts)],      # anim: how the viewer moves this part (see web/models.html)
                 size=[round(max(xs) - min(xs)), round(max(ys) - min(ys)), round(max(zs) - min(zs))], tex=base.get('tex'), tex_arc=base.get('tex_arc'))
    if cfg.get('pivot'): entry['pivot'] = cfg['pivot']        # [x, y] in model units: the viewers centre and turn the whole model about this vertical axis instead of the middle of its bounding box (Hell Atsche: the central gun stand)
    print(cfg['id'], [(len(p.V), len(p.Q)) for p, _ in parts], 'size', entry['size'])
    return entry

if __name__ == '__main__':
    entries = [build(json.load(open(f, encoding='utf8'))) for f in sorted(glob.glob(os.path.join(ROOT, 'data/composite_*.json')))]
    import build_drydock; entries += build_drydock.build_all()          # the eight drydocks from MAP.BIN (not described by a data/composite_*.json: they come straight from the game files)
    json.dump(entries, open(os.path.join(MODELS, 'composites.json'), 'w', encoding='utf8'), separators=(',', ':'), ensure_ascii=False)
    print(len(entries), 'composites')
