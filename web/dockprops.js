/* Dock scenery props for the Models page (the dock page, drydock.html, has its own copy of this logic).
   Data: models/dock_objects.json (tools/build_dock_objects.py: PSM0 placement rows + BEV 90-97 spawns) and models/index.json; models/<chr_id>.bin / .png.
   DockProps.build(n, centre, opts) -> Promise<THREE.Group> in MODEL space (z-up, units of 1/4096 map unit), positions minus `centre` (a THREE.Vector3), to be rotated -90 deg about X like the dock meshes.
   Scale: the common x10 (inferred, see notes/drydock.md); the three crane models x3 more (30). Facing: row ids 90 + 45 x (id >> 16) degrees; script props use yaw + 270 / + 90 (AA mounts / others),
   the four AA mounts on the big hull at -x. Lights (every slot-12 part and dark flare triangles) are drawn additive and hidden (day). */
window.DockProps = (function () {
  var data = null, index = null, lightInfo = {}, loading = null, geoCache = {}, texCache = {};
  var SCALE = 10, MULT = { 15: 3, 16: 3, 20: 3 }, LOWER = { 7: 510 };
  function load() {
    if (!loading) loading = Promise.all([fetch('models/dock_objects.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }), fetch('models/index.json').then(function (r) { return r.json(); }), fetch('models/dock_lights.json', { cache: 'no-cache' }).then(function (r) { return r.json(); })])
      .then(function (a) { data = a[0]; index = {}; a[1].forEach(function (m) { index[m.id] = m; }); lightInfo = a[2]; }).catch(function () { data = {}; index = {}; lightInfo = {}; });
    return loading;
  }
  function geometry(dv, off, p) {
    var qo = off + p.v * 12, uo = qo + p.q * 8, pos = [], uv = [];
    for (var k = 0; k < p.q; k++) {
      var q4 = [0, 1, 2, 3].map(function (j) { return dv.getUint16(qo + (k * 4 + j) * 2, true); });
      (q4[2] === q4[3] ? [[0, 1, 2]] : [[0, 1, 2], [0, 2, 3]]).forEach(function (t) { t.forEach(function (c) {
        var vi = q4[c]; pos.push(dv.getFloat32(off + vi * 12, true), dv.getFloat32(off + vi * 12 + 4, true), dv.getFloat32(off + vi * 12 + 8, true));
        uv.push(dv.getUint16(uo + (k * 8 + c * 2) * 2, true) / 16384, dv.getUint16(uo + (k * 8 + c * 2 + 1) * 2, true) / 16384); }); });
    }
    var g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); return g;
  }
  function tex(id) {
    if (!texCache[id]) texCache[id] = new Promise(function (res) { new THREE.TextureLoader().load('models/' + id + '.png', function (t) { t.flipY = false; t.wrapS = t.wrapT = THREE.RepeatWrapping; res(t); }, undefined, function () { res(null); }); });
    return texCache[id];
  }
  function model(id) {
    if (geoCache[id]) return geoCache[id];
    return geoCache[id] = (async function () {
      var m = index[id]; if (!m) return null;
      var buf = await (await fetch('models/' + id + '.bin')).arrayBuffer(), dv = new DataView(buf), off = 0, geos = [], t = m.tex != null ? await tex(id) : null;
      // body = slot 0 only; the light faces (face flag bit 0x100 in slot 12, exported by tools/export_dock_lights.py) are drawn additive and hidden by day
      m.parts.forEach(function (p) { if (p.kind === 'mesh' && p.slot !== 12) geos.push(geometry(dv, off, p)); off += p.v * 12 + p.q * 24; });
      var out = geos.map(function (g) { return { g: g, glow: false }; });
      if (lightInfo[id]) { try { var lb = await (await fetch('models/' + id + '_L.bin')).arrayBuffer(); out.push({ g: geometry(new DataView(lb), 0, lightInfo[id]), glow: true }); } catch (e) {} }
      return { geos: out, tex: t };
    })();
  }
  function yawOf(o) {
    if (o.j === 41 && o.x > 10 && o.z < 1.5) return Math.PI / 4 + (o.yaw + 0.8);        // the four AA mounts on the big hull
    return o.yaw !== undefined ? o.yaw + (o.j === 41 ? 3 * Math.PI / 2 : Math.PI / 2) : (90 + o.v * 45) * Math.PI / 180;
  }
  async function build(n, centre, opts) {
    await load(); opts = opts || {};
    var group = new THREE.Group(), list = (data && data[String(n)]) || [], s0 = opts.scale || SCALE;
    for (var i = 0; i < list.length; i++) {
      var o = list[i], mo = o.model && await model(o.model); if (!mo) continue;
      mo.geos.forEach(function (e) {
        var mat = new THREE.MeshStandardMaterial({ color: mo.tex ? 0xffffff : 0x8fb4d8, map: mo.tex, metalness: 0.05, roughness: 0.85, side: THREE.DoubleSide, transparent: !!mo.tex, alphaTest: mo.tex ? 0.4 : 0 });
        if (e.glow) { mat.blending = THREE.AdditiveBlending; mat.depthWrite = false; mat.alphaTest = 0; mat.transparent = true; mat.emissive = new THREE.Color(0xffffff); mat.emissiveMap = mo.tex; mat.color.set(0x000000); }
        var m = new THREE.Mesh(e.g, mat), s = s0 * (MULT[o.j] || 1); m.frustumCulled = false; m.userData.glow = !!e.glow; m.visible = !e.glow;
        m.scale.setScalar(s); m.rotation.z = yawOf(o);
        m.position.set(o.x * 4096 - centre.x, o.y * 4096 - centre.y, o.z * 4096 - (LOWER[o.j] || 0) * s - centre.z);
        group.add(m);
      });
    }
    return group;
  }
  return { build: build, load: load };
})();
