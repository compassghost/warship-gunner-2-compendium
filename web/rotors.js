/* Aircraft rotors for the thumbnail viewers (same rules as designer3d.html's loadModel, which still has its own copy).
   wg2Rotors(m, buf, id) -> { body: {pos, uv}, rots: [{pos, uv, c, axis, n}] }
   Only the high-poly model (part 0) is drawn. Its rotor blades / propeller blades / tail rotor become separate pieces that spin about a hub c (axis 'x' | 'y' | 'z', or the
   unit normal n of a tilted disc). The low-poly copy (part 1) is never drawn: its flat blur discs only give the hub, the axis and the height of each main rotor / propeller.
   Model coordinates (z up, the nose is -y). A rotor with no high-poly blades to spin is not drawn. */
function wg2Rotors(m, buf, id) {
  const dv = new DataView(buf), heli = m.cls === 'Helicopter', body = { pos: [], uv: [] }, rots = [];
  const tailQ = [], bladeQ = [], mainD = [], discQ = [], propQ = [], triQ = [];
  const bb = pos => { const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9]; for (let i = 0; i < pos.length; i += 3) for (let a = 0; a < 3; a++) { if (pos[i + a] < lo[a]) lo[a] = pos[i + a]; if (pos[i + a] > hi[a]) hi[a] = pos[i + a]; } return { lo, hi, e: [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]], c: [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2] }; };
  const addBody = b => { for (const v of b.pos) body.pos.push(v); for (const v of b.uv) body.uv.push(v); };
  const join = L => { const o = { pos: [], uv: [] }; for (const b of L) { for (const v of b.pos) o.pos.push(v); for (const v of b.uv) o.uv.push(v); } return o; };
  let off = 0;
  for (const p of m.parts) {
    if (p.kind === 'mesh' && p.slot !== 12) {
      const qo = off + p.v * 12, uo = qo + p.q * 8, quads = [];
      for (let k = 0; k < p.q; k++) {
        const ix = [0, 1, 2, 3].map(j => dv.getUint16(qo + (k * 4 + j) * 2, true)); if (Math.max(...ix) >= p.v) continue;
        const pos = [], uv = [];
        for (const t of (ix[2] === ix[3] ? [[0, 1, 2]] : [[0, 1, 2], [0, 2, 3]])) for (const c of t) { const vi = ix[c]; pos.push(dv.getFloat32(off + vi * 12, true), dv.getFloat32(off + vi * 12 + 4, true), dv.getFloat32(off + vi * 12 + 8, true)); uv.push(dv.getUint16(uo + (k * 8 + c * 2) * 2, true) / 16384, dv.getUint16(uo + (k * 8 + c * 2 + 1) * 2, true) / 16384); }
        quads.push({ ix, pos, uv });
      }
      const par = []; for (let i = 0; i < p.v; i++) par[i] = i;
      const fnd = a => { while (par[a] !== a) a = par[a] = par[par[a]]; return a; };
      for (const q of quads) for (let j = 1; j < 4; j++) { const a = fnd(q.ix[0]), b = fnd(q.ix[j]); if (a !== b) par[a] = b; }
      const cl = new Map(); for (const q of quads) { const k = fnd(q.ix[0]); if (!cl.has(k)) cl.set(k, { pos: [], uv: [] }); const C = cl.get(k); for (const v of q.pos) C.pos.push(v); for (const v of q.uv) C.uv.push(v); }
      if (p.slot > 0) {      // low-poly copy: only its flat blur discs are used, as hub / axis / height markers
        for (const C of cl.values()) {
          const b = bb(C.pos), [ex, ey, ez] = b.e;
          if (heli) { if (ez < 2 && ex > 1000 && ey > 1000 && Math.abs(ex - ey) < 0.15 * Math.max(ex, ey)) mainD.push({ pos: C.pos, uv: C.uv, c: b.c.slice(), bl: [] }); }
          else if (ey < 2 && ex > 250 && ez > 250 && Math.abs(ex - ez) < 0.03 * Math.max(ex, ez) && C.pos.length <= 54) discQ.push({ pos: C.pos, uv: C.uv, c: b.c });
        }
      } else if (heli) {
        for (const C of cl.values()) {
          const b = bb(C.pos), [ex, ey, ez] = b.e; let tn = null;
          if (C.pos.length >= 9) { const P = C.pos, e1 = [P[3] - P[0], P[4] - P[1], P[5] - P[2]], e2 = [P[6] - P[0], P[7] - P[1], P[8] - P[2]], n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]], l = Math.hypot(...n); if (l > 0) tn = n.map(x => x / l); }
          if (tn && Math.abs(tn[0]) > 0.9 && ey > 180 && ey < 700 && ez > 180 && ez < 700 && Math.abs(ey - ez) < 0.2 * Math.max(ey, ez) && C.pos.length <= 54 && Math.abs(b.c[1]) > 700) tailQ.push({ pos: C.pos, uv: C.uv, c: b.c, n: tn });      // tail rotor: a nearly round side disc far forward or aft (the Black Hawk's is canted)
          else if (ez < 2 && Math.max(ex, ey) > 600 && C.pos.length <= 144) bladeQ.push({ pos: C.pos, uv: C.uv, c: b.c });      // main rotor blade: a flat quad (or two) more than 600 units long
          else addBody(C);
        }
      } else {
        for (const q of quads) {      // other aircraft, per quad
          const b = bb(q.pos), ry = Math.max(...q.pos.filter((_, i) => i % 3 === 1).map(Math.abs));
          if (id === 'chr_965' && ry <= 160 && Math.hypot(b.c[0], b.c[2]) > 160) triQ.push(q);      // Triebfluegel: the whole rotor (arms, blades, engines) turns together about the y axis
          else if (b.e[1] < 2 && Math.max(b.e[0], b.e[2]) > 150) propQ.push({ y: b.c[1], c: b.c, pos: q.pos, uv: q.uv });      // a flat forward-facing quad: a propeller blade
          else addBody(q);
        }
      }
    }
    off += p.v * 12 + p.q * 24;
  }
  // tail rotors: pieces with the same centre turn together about the disc normal
  const tg = new Map(); for (const t of tailQ) { const k = t.c.map(x => Math.round(x / 80)).join(); if (!tg.has(k)) tg.set(k, []); tg.get(k).push(t); }
  for (const L of tg.values()) rots.push({ ...join(L), c: L[0].c, axis: 'x', n: L[0].n });
  if (triQ.length) rots.push({ ...join(triQ), c: [0, 0, 0], axis: 'y' });
  // helicopter main rotors: blades (grouped by height) go to the nearest low-poly disc at their height; the disc gives the hub (a lopsided one is centred on the mast)
  for (const d of mainD) if (Math.abs(d.c[0]) < 200 && Math.abs(d.c[1]) < 200) { d.c[0] = 0; d.c[1] = 0; }
  const hg = new Map(); for (const b of bladeQ) { const k = Math.round(b.c[2] / 80); if (!hg.has(k)) hg.set(k, []); hg.get(k).push(b); }
  for (const L of hg.values()) {
    if (L.length < 3) { L.forEach(addBody); continue; }      // fewer than 3 flat pieces at one height are not a rotor
    for (const b of L) { let best = null, bd = 1e12; for (const d of mainD) { if (Math.abs(d.c[2] - b.c[2]) > 60) continue; const dd = Math.hypot(d.c[0] - b.c[0], d.c[1] - b.c[1]); if (dd < bd) { bd = dd; best = d; } } if (best) best.bl.push(b); else addBody(b); }
  }
  for (const d of mainD) { if (d.bl.length >= 3) rots.push({ ...join(d.bl), c: d.c, axis: 'z' }); else d.bl.forEach(addBody); }
  // propeller discs (the two faces of one disc share a centre) take the blades at their level
  const dg = new Map(); for (const d of discQ) { const k = d.c.map(x => Math.round(x / 30)).join(); if (!dg.has(k)) dg.set(k, { c: d.c, bl: [] }); }
  const pd = [...dg.values()];
  for (const b of propQ) { let best = null, bd = 1e12; for (const d of pd) { if (Math.abs(d.c[1] - b.y) > 40) continue; const dd = Math.hypot(d.c[0] - b.c[0], d.c[2] - b.c[2]); if (dd < bd) { bd = dd; best = d; } } if (best) best.bl.push(b); else addBody(b); }
  for (const d of pd) if (d.bl.length) rots.push({ ...join(d.bl), c: d.c, axis: 'y' });
  return { body, rots };
}
