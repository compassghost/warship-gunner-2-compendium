"""PSC1 model container (CHR.BIN, MDT_SHIP.BIN, MDT_WEPH.BIN, MDT_WEPL.BIN). Layout as decoded in the model audit (notes/model_audit.md).

Header (little-endian):
  0x00 'PSC1'; u8 [4] = number of nodes; u8 [5] = number of part slots; u16 [8] flags (2 normal, +8 = 32-bit vertices, +32 = effect);
  u16 [0x0a] = number of animation frames; u16 [0x0c] = number of position entries; u16 [0x0e] = number of rotation entries;
  u32 [0x18] animation table, [0x1c] hierarchy (child lists, 0xff-terminated), [0x20] position table (8 bytes: s16 x, y, z, u16 scale, 1024 = 1.0,
  0 = hidden), [0x24] rotation table (6 bytes: s16 x, y, z, 65536 = 360 degrees), [0x34] node flags, [0x38] = B (size of the header block; all
  part pointers are relative to B), [0x3c] -> model name (ASCII, e.g. 'U_HE_03', 'BOS12'), [0x40 + 4*i] -> part slot i (0 = unused).

Part slots are separate meshes of the same object: slot 0 the full-detail mesh, slots 1-2 lower levels of detail (bytes [5..7] of a part list its
lower-detail slots), slot 4 (ships, bosses, map objects) an untextured collision hull.

Part record: u16 vertex count, u16 face count, u8[4] detail chain, u32 x3 switch distances, u32 0x40, then pointers (relative to B):
  [0x18] vertices: 4-byte prefix + 10-byte records (s16 x, y, z, u16, u16 id), or with header flag 8: 16-byte records (u16, u16 id, s32 x, y, z);
  [0x1c] faces (24 bytes, see below); [0x20] colour table (3 bytes per entry, 0x80 = neutral); [0x24] texture-coordinate records (20 bytes:
  four (u, v) u16 pairs, /16384, v down from the top of the image; then 4 attribute bytes); [0x28] float normals (12 bytes); [0x34] vertex normals;
  u16 [0x38] colour count, u16 [0x3a] UV record count, u32 [0x3c] normal count; then at +0x40 one 20-byte record per node:
  u16 first vertex, u16 end vertex, u16 first face, u16 end face, u16 radius-like value, u16 parent node (| 0x8000; without the bit the node is a
  root), u32 -> child list, u32 -> animation track (one (position index, rotation index) u16 pair per frame; 0xffff = no rotation).

Face record (24 bytes): four u16 vertex indices a, b, c, e in outline order (a triangle when e == c); u8 flags, u8 flags; u16 colour index;
u16 [12] material value; u16 [14] = index of the face's UV record (bit 15 set or 0xffff = the face has no texture); three u16 0xffff; u16 [22] =
normal index. UV records are SHARED between faces (a model has far fewer records than faces), so they must be looked up through [14]; reading
them in face order is what scrambled the textures before.

Node placement: a node's vertices are local. World position = parent transform applied to (rotation * vertex * scale + position * POS_SCALE),
where POS_SCALE is 2 vertex units per position unit (8 for the 32-bit vertex models). Frame 0 of the animation track is the rest pose; other
frames are animation steps (rotor / turret angles) or damage states (scale 0 hides a node)."""
import struct, math

def _u16(d, o): return struct.unpack_from('<H', d, o)[0]
def _u32(d, o): return struct.unpack_from('<I', d, o)[0]

def _rot(r):
    """Rotation matrix from (x, y, z) angles, 65536 = full turn; applied as Rz * Ry * Rx."""
    M = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    for axis, a in (('z', r[2]), ('y', r[1]), ('x', r[0])):
        if not a: continue
        t = a * 2 * math.pi / 65536; c, s = math.cos(t), math.sin(t)
        R = {'x': [[1, 0, 0], [0, c, -s], [0, s, c]], 'y': [[c, 0, s], [0, 1, 0], [-s, 0, c]], 'z': [[c, -s, 0], [s, c, 0], [0, 0, 1]]}[axis]
        M = _mul(M, R)
    return M
def _mul(A, B): return [[A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j] for j in range(3)] for i in range(3)]
def _app(M, v): return (M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2], M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2], M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2])
_ID = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]

def child_parents(part):
    """Parent of every node as given by the child lists (what the game walks); None = no parent. Differs from the node record's parent field + bit 15
    (BOS05A: the bridge and weapons have no bit 15 but are children of the hull in the child lists, so they must follow it)."""
    par = {}
    for k, n in enumerate(part['nodes']):
        for c in n.get('children', []):
            if c < len(part['nodes']) and c != k and c not in par: par[c] = k
    return par

def hier_parents(part, children=True):
    """Parent of every node (list, None = root). children=True: the child lists first (what the game walks), and the old rule (parent field, bit 15 = has a parent)
    only for nodes that are in no child list. children=False: the old rule alone."""
    cp = child_parents(part) if children else {}
    out = []
    for k, n in enumerate(part['nodes']):
        if k in cp: out.append(cp[k])
        else: out.append(None if n['root'] or n['parent'] == k or n['parent'] >= len(part['nodes']) else n['parent'])
    return out

def node_transforms(model, part, frame=0, children=True):
    """Per node: (3x3 rotation, translation in vertex units, scale) in model space for one animation frame.
    children=True (default since 2026-11-15) takes the hierarchy from the child lists (see hier_parents); children=False is the old parent-field rule."""
    ps = model['pos_scale']; out = {}
    hp = hier_parents(part, children)
    def get(k, depth=0):
        if k in out: return out[k]
        n = part['nodes'][k]
        pi, ri = n['track'][min(frame, len(n['track']) - 1)] if n['track'] else (0, 0xffff)
        p = model['pos'][pi] if pi < len(model['pos']) else (0, 0, 0, 1024)
        R = _rot(model['rot'][ri]) if ri < len(model['rot']) else _ID
        T = (p[0] * ps, p[1] * ps, p[2] * ps); s = p[3] / 1024
        parent = hp[k]
        if parent is not None and depth < 64:
            PR, PT, PS = get(parent, depth + 1)
            t = _app(PR, T); T = (t[0] * PS + PT[0], t[1] * PS + PT[1], t[2] * PS + PT[2]); R = _mul(PR, R); s *= PS
        out[k] = (R, T, s); return out[k]
    for k in range(len(part['nodes'])): get(k)
    return out

def bake(model, part, frame=0, children=True):
    """Vertices of a part in model space (node transforms of the given frame applied)."""
    V = [tuple(float(c) for c in v) for v in part['local_verts']]
    T = node_transforms(model, part, frame, children)
    for k, n in enumerate(part['nodes']):
        R, t, s = T[k]
        if R is _ID and t == (0, 0, 0) and s == 1: continue
        for i in range(n['verts'][0], min(n['verts'][1], len(V))):
            w = _app(R, V[i]); V[i] = (w[0] * s + t[0], w[1] * s + t[1], w[2] * s + t[2])
    return V

def parse_model(d):
    assert d[:4] == b'PSC1'
    B = _u32(d, 0x38); nn = d[4]; nslots = d[5]; flags = _u16(d, 8); nfr = _u16(d, 10); npos = _u16(d, 12); nrot = _u16(d, 14)
    o_pos, o_rot, o_nf, o_name = _u32(d, 0x20), _u32(d, 0x24), _u32(d, 0x34), _u32(d, 0x3c)
    big = bool(flags & 8)
    model = dict(name=d[o_name:o_name + 16].split(b'\0')[0].decode('latin1') if o_name else '', flags=flags, frames=nfr, big=big, pos_scale=8 if big else 2,
                 pos=[struct.unpack_from('<3hH', d, o_pos + 8 * k) for k in range(npos)], rot=[struct.unpack_from('<3h', d, o_rot + 6 * k) for k in range(nrot)], parts=[])
    for i in range(nslots):
        o = _u32(d, 0x40 + 4 * i)
        if not o: continue
        nv, nf = _u16(d, o), _u16(d, o + 2)
        W = [_u32(d, o + 4 * k) for k in range(16)]
        ncol, nuv = _u16(d, o + 0x38), _u16(d, o + 0x3a)
        vo, fo, co, uo = B + W[6], B + W[7], B + W[8], B + W[9]
        wide = nv > 0 and (fo - vo) // nv >= 15
        if wide: LV = [struct.unpack_from('<3i', d, vo + 16 * k + 4) for k in range(nv)]
        else: LV = [struct.unpack_from('<3h', d, vo + 4 + 10 * k) for k in range(nv)]
        recs = [struct.unpack_from('<8H', d, uo + 20 * j) for j in range(nuv)]
        attrs = [d[uo + 20 * j + 16: uo + 20 * j + 20] for j in range(nuv)]
        quads, uvs, uvi, fflags, fcol, bad = [], [], [], [], [], 0
        for k in range(nf):
            a, b, c, e, f8, f9, col, mat, ui = struct.unpack_from('<4H2B3H', d, fo + 24 * k)
            if max(a, b, c, e) >= nv: bad += 1; continue
            quads.append((a, b, c, e)); fflags.append(f8 | f9 << 8); fcol.append(col)
            if ui < nuv: uvs.append(recs[ui]); uvi.append(ui)
            else: uvs.append((0,) * 8); uvi.append(None)            # bit 15 / 0xffff: untextured face
        nodes = []
        for k in range(nn):
            vs, ve, fs, fe, rad, par, pc, pt = struct.unpack_from('<6H2I', d, o + 0x40 + 20 * k)
            track = [struct.unpack_from('<2H', d, pt + 4 * f) for f in range(nfr)] if pt else []
            kids = []                                                                  # child list: node numbers, 0xff-terminated, at an absolute file offset (0 = none)
            if pc and pc < len(d):
                while len(kids) < 64 and pc + len(kids) < len(d) and d[pc + len(kids)] != 0xff: kids.append(d[pc + len(kids)])
            nodes.append(dict(verts=(vs, ve), faces=(fs, fe), radius=rad, parent=par & 0x7fff, root=not (par & 0x8000), track=track, flag=_u32(d, o_nf + 4 * k) if o_nf else 0, children=kids))
        part = dict(slot=i, lod=tuple(d[o + 5:o + 8]), local_verts=LV, quads=quads, uvs=uvs, uv_index=uvi, face_flags=fflags, face_colour=fcol, uv_attrs=attrs,
                    colours=[tuple(d[co + 3 * k: co + 3 * k + 3]) for k in range(ncol)], nodes=nodes, raw_faces=nf, bad_faces=bad, uv_records=nuv, words=W)
        part['verts'] = bake(model, part, 0)
        F = []
        for a, b, c, e in quads:
            F.append((a, b, c))
            if e != c: F.append((a, c, e))
        part['faces'] = F
        ntex = sum(1 for u in uvi if u is not None)
        part['kind'] = 'empty' if not quads else 'collision' if ntex * 2 < len(quads) else 'mesh'      # a collision hull has (almost) no textured faces
        model['parts'].append(part)
    return model

def parse(d):
    """Backwards-compatible: the list of parts (keys slot, verts, faces, quads, uvs, raw_faces, words, ...)."""
    return parse_model(d)['parts']
