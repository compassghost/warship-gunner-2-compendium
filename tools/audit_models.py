"""Audit of every PSC1 model: texture mapping coverage, faces without texture, texture / UV agreement, holes, multi-part placement.
Writes data/model_audit.json (per model) and prints a summary. notes/model_audit.md is the written-up result.
Run: python tools/audit_models.py"""
import os, sys, json, math, struct
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import psc1, model_entities
ROOT = os.path.join(os.path.dirname(__file__), '..')

def tex_info(d):
    """-> (w, h, alpha per pixel as bytes, palette) or None."""
    if d[:6] == b'SHTXFS': w, h = 1 << d[10], 1 << d[11]; hdr = 12
    elif d[:6] == b'SHTXST':
        hdr = 8; n = len(d) - 1032; s = math.isqrt(n)
        w, h = (s, s) if s * s == n else (math.isqrt(n // 2) * 2, math.isqrt(n // 2))
        if w * h != n: return None
    else: return None
    pal = d[hdr:hdr + 1024]; data = d[hdr + 1024:hdr + 1024 + w * h]
    if len(data) != w * h: return None
    al = bytes(pal[4 * i + 3] for i in range(256))
    return w, h, data.translate(al)

def old_rule(kinds, e):
    for t in (e - 1, e + 1):
        if 0 <= t < len(kinds) and kinds[t][:4] == b'SHTX': return t
    return None

def audit():
    ents = model_entities.build(); arcs = {a: model_entities.Arc(a) for a in model_entities.MODEL_ARCS}
    kinds = {a: [] for a in arcs}
    for a, A in arcs.items():
        for e in range(len(A.idx)):
            try: kinds[a].append(A.get(e)[:6])
            except Exception: kinds[a].append(b'')
    texc = {}
    def tex(ref):
        ref = tuple(ref)
        if ref not in texc:
            try: texc[ref] = tex_info(arcs[ref[0]].get(ref[1]))
            except Exception: texc[ref] = None
        return texc[ref]
    rows = []
    for info in ents:
        A = arcs[info['archive']]; e = info['entry']
        model = psc1.parse_model(A.get(e))
        ti = tex(info['texture']) if info['texture'] else None
        row = dict(id=info['id'], name=info['name'], category=info['category'], entities=info['entities'] or info['entities_inferred'], texture=info['texture'],
                   old_texture=old_rule(kinds[info['archive']], e), frames=model['frames'], parts=[])
        row['texture_changed'] = bool(info['texture']) and (info['texture'][0] != info['archive'] or info['texture'][1] != row['old_texture'])
        for p in model['parts']:
            q = p['quads']
            if not q: continue
            V = p['verts']; untex = [k for k, u in enumerate(p['uv_index']) if u is None]
            # degenerate faces (fewer than 3 distinct corners)
            degen = sum(1 for a, b, c, e4 in q if len({a, b, c}) < 3)
            # texture / UV agreement: UV range, and where the face centre lands in the texture (alpha 0 = cut out)
            out_of_range = 0; transparent = 0; sampled = 0
            for k, (a, b, c, e4) in enumerate(q):
                if p['uv_index'][k] is None: continue
                u = p['uvs'][k]; n = 3 if e4 == c else 4
                us = [u[2 * j] / 16384 for j in range(n)]; vs = [u[2 * j + 1] / 16384 for j in range(n)]
                if max(us) > 1.002 or max(vs) > 1.002: out_of_range += 1
                if ti:
                    w, h, al = ti; cu, cv = sum(us) / n, sum(vs) / n
                    x = min(w - 1, int(cu % 1.0 * w)); y = min(h - 1, int(cv % 1.0 * h)); sampled += 1
                    if al[y * w + x] == 0: transparent += 1
            # holes: boundary edges after welding vertices by position (nodes duplicate vertices along seams)
            key = {}; ids = []
            for v in V:
                kk = (round(v[0]), round(v[1]), round(v[2])); ids.append(key.setdefault(kk, len(key)))
            edges = Counter()
            for a, b, c, e4 in q:
                cyc = [ids[a], ids[b], ids[c]] + ([ids[e4]] if e4 != c else [])
                for j in range(len(cyc)):
                    x, y = cyc[j], cyc[(j + 1) % len(cyc)]
                    if x != y: edges[(min(x, y), max(x, y))] += 1
            open_edges = sum(1 for n in edges.values() if n == 1)
            # nodes
            T = psc1.node_transforms(model, p, 0); placed = []; hidden = []
            for k, n in enumerate(p['nodes']):
                if n['verts'][1] <= n['verts'][0]: continue
                R, t, s = T[k]
                if s == 0: hidden.append(k)
                animated = len(set(n['track'])) > 1
                placed.append(dict(node=k, parent=n['parent'], verts=n['verts'][1] - n['verts'][0], offset=[round(x) for x in t], rotated=R is not psc1._ID and R != psc1._ID,
                                   animated=animated))
            untex_detail = Counter()
            for k in untex: untex_detail[(p['face_flags'][k], p['face_colour'][k], p['colours'][p['face_colour'][k]] if p['face_colour'][k] < len(p['colours']) else None)] += 1
            row['parts'].append(dict(slot=p['slot'], kind=p['kind'], verts=len(V), faces=len(q), uv_records=p['uv_records'], untextured=len(untex), bad_index_faces=p['bad_faces'],
                                     degenerate=degen, uv_out_of_range=out_of_range, transparent_centres=transparent, sampled=sampled, open_edges=open_edges, edges=len(edges),
                                     nodes=placed, hidden_nodes=hidden, untextured_detail=[dict(flags=f, colour_index=c, colour=col, faces=n) for (f, c, col), n in untex_detail.most_common(6)]))
        rows.append(row)
    return rows

if __name__ == '__main__':
    rows = audit()
    json.dump(rows, open(os.path.join(ROOT, 'data/model_audit.json'), 'w', encoding='utf8'), ensure_ascii=False)
    mesh = [(r, p) for r in rows for p in r['parts'] if p['kind'] == 'mesh']; coll = [(r, p) for r in rows for p in r['parts'] if p['kind'] == 'collision']
    F = sum(p['faces'] for r, p in mesh); U = sum(p['untextured'] for r, p in mesh)
    print(len(rows), 'models;', len(mesh), 'textured meshes with', F, 'faces,', U, 'without texture (%.3f%%)' % (100 * U / F))
    print(len(coll), 'collision meshes with', sum(p['faces'] for r, p in coll), 'faces,', sum(p['faces'] - p['untextured'] for r, p in coll), 'of them textured')
    print('bad index faces', sum(p['bad_index_faces'] for r, p in mesh + coll), 'degenerate', sum(p['degenerate'] for r, p in mesh))
    print('models whose texture differs from the old neighbour rule:', sum(1 for r in rows if r['texture_changed']))
    print('meshes with untextured faces:', sum(1 for r, p in mesh if p['untextured']))
    print('multi-node meshes (slot 0):', sum(1 for r, p in mesh if p['slot'] == 0 and len(p['nodes']) > 1), '; with a node moved off the origin:',
          sum(1 for r, p in mesh if p['slot'] == 0 and any(any(n['offset']) for n in p['nodes'])))
