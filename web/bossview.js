/* Live 3D boss viewers for bosses.html. Same approach as the superweapon viewers on campaign.html: ALL viewers share one WebGL renderer, which every frame draws each
   visible model into its own plain 2D canvas at that canvas's real pixel size, slowly turning (a browser only allows a handful of WebGL contexts).
   bossView(id, ratio, canvas): starts loading when the canvas scrolls into view. Models are single exported models (models/index.json) or assembled bosses
   (models/composites.json, entries with "all": every part drawn together with its own texture). */
(function () {
  var modelIdx = null, liveR = null, lastT = null, BUF_W = 3000, BUF_H = 2000, VIEW_W = 3000, VIEW_H = 2000, live = new Set();
  var calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var PIVOTS = { composite_hell_atsche: [0, 0] };        // fallback for models/composites.json entries without a "pivot" (data/composite_hell_atsche.json): the central gun stand's axis
  var visIO = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.target._live) e.target._live.vis = e.isIntersecting; }); });
  var startIO = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { startIO.unobserve(e.target); var a = e.target._args; start(a[0], a[1], e.target); } }); }, { rootMargin: '200px' });

  function geometry(dv, p) {
    var qo = p.v * 12, uo = qo + p.q * 8, pos = [], uv = [];
    for (var k = 0; k < p.q; k++) {
      var q4 = [0, 1, 2, 3].map(function (j) { return dv.getUint16(qo + (k * 4 + j) * 2, true); });
      var tris = q4[2] === q4[3] ? [[0, 1, 2]] : [[0, 1, 2], [0, 2, 3]];
      tris.forEach(function (t) { t.forEach(function (c) {
        var vi = q4[c]; pos.push(dv.getFloat32(vi * 12, true), dv.getFloat32(vi * 12 + 4, true), dv.getFloat32(vi * 12 + 8, true));
        uv.push(dv.getUint16(uo + (k * 8 + c * 2) * 2, true) / 16384, dv.getUint16(uo + (k * 8 + c * 2 + 1) * 2, true) / 16384);
      }); });
    }
    var g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); g.computeBoundingBox();
    return g;
  }
  function material(tex) {
    if (tex) { tex.flipY = false; tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.encoding = THREE.sRGBEncoding; }
    return new THREE.MeshStandardMaterial({ color: tex ? 0xffffff : 0x8fb4d8, map: tex, metalness: 0.05, roughness: 0.8, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1, transparent: !!tex, alphaTest: tex ? 0.4 : 0 });
  }
  function loadTex(name) { return new Promise(function (res) { new THREE.TextureLoader().load('models/' + name + '.png', res, undefined, function () { res(null); }); }); }
  async function start(id, ratio, cv) {
    if (!window.THREE) return;
    if (!modelIdx) modelIdx = Promise.all([fetch('models/index.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }), fetch('models/composites.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).catch(function () { return []; })]).then(function (x) { return x[0].concat(x[1]); });
    var m = (await modelIdx).find(function (x) { return x.id === id; }); if (!m) return;
    var buf = await (await fetch('models/' + id + '.bin', { cache: 'no-cache' })).arrayBuffer(); if (!cv.isConnected) return;
    var parts = m.all ? m.parts : [m.parts[0]], gs = [], texs = [], off = 0;
    parts.forEach(function (p) { var dv = new DataView(buf, m.all ? off : 0); gs.push(geometry(dv, p)); if (m.all) off += p.v * 12 + p.q * 24; });
    var box = new THREE.Box3(); gs.forEach(function (g) { box.union(g.boundingBox); }); var ctr = new THREE.Vector3(); box.getCenter(ctr); var r = 0;
    var pv = m.pivot || PIVOTS[m.id];                                                        // the entry's own pivot (models/composites.json), or the fallback table below
    if (m.all && pv) { ctr.x = pv[0]; ctr.y = pv[1]; }                                        // turn about the composite's own vertical axis (Hell Atsche: the central gun stand), not the middle of its bounding box
    gs.forEach(function (g) { g.translate(-ctr.x, -ctr.y, -ctr.z); g.computeBoundingSphere(); r = Math.max(r, g.boundingSphere.center.length() + g.boundingSphere.radius); });
    if (m.all) texs = await Promise.all(parts.map(function (p) { return loadTex(p.texid); }));
    else texs = [m.tex != null ? await loadTex(id) : null];
    if (!cv.isConnected) { gs.forEach(function (g) { g.dispose(); }); return; }
    var grp = new THREE.Group(), mats = [];
    gs.forEach(function (g, i) { var mt = material(texs[i]); mats.push(mt); grp.add(new THREE.Mesh(g, mt)); });
    grp.rotation.x = -Math.PI / 2; grp.rotation.z = 0.7;                                   // model data is z-up; turn about the up axis
    var scene = new THREE.Scene(); scene.add(grp); scene.add(new THREE.HemisphereLight(0xffffff, 0x667788, 1.6)); var dl = new THREE.DirectionalLight(0xffffff, 1.0); dl.position.set(1, 2, 1.5); scene.add(dl);
    var dist = r * Math.hypot(0.8, 2.8), cam = new THREE.PerspectiveCamera(35, ratio, dist - r * 1.05, dist + r * 1.05); cam.position.set(0, r * 0.8, r * 2.8); cam.lookAt(0, 0, 0);   // near / far hug the bounding sphere (depth precision)
    if (!liveR) {
      liveR = new THREE.WebGLRenderer({ antialias: true, alpha: true }); liveR.setPixelRatio(1); liveR.setSize(VIEW_W, VIEW_H, false);
      var gl = liveR.getContext(); if (gl.drawingBufferWidth !== VIEW_W || gl.drawingBufferHeight !== VIEW_H) liveR.setSize(gl.drawingBufferWidth, gl.drawingBufferHeight, false);
      BUF_W = gl.drawingBufferWidth; BUF_H = gl.drawingBufferHeight; liveR.setClearColor(0x000000, 0); requestAnimationFrame(frame);
    }
    var rc = cv.getBoundingClientRect();                                                    // start with the real position; the observer only keeps it up to date afterwards
    var it = { cv: cv, ratio: ratio, scene: scene, cam: cam, mesh: grp, g: gs, tex: texs.filter(Boolean), mats: mats, vis: rc.width > 0 && rc.bottom > 0 && rc.top < innerHeight }; cv._live = it; live.add(it); visIO.observe(cv);
  }
  function frame(t) {
    var dt = lastT === null ? 0 : Math.min(50, t - lastT); lastT = t; var dpr = Math.min(2, devicePixelRatio || 1);
    live.forEach(function (it) {
      if (!it.cv.isConnected) { it.g.forEach(function (g) { g.dispose(); }); it.tex.forEach(function (x) { x.dispose(); }); it.mats.forEach(function (x) { x.dispose(); }); live.delete(it); visIO.unobserve(it.cv); return; }
      var cw = it.cv.clientWidth; if (!it.vis || !cw) return;
      var W = Math.min(BUF_W, Math.round(cw * dpr)), H = Math.round(W / it.ratio); if (H > BUF_H) { H = BUF_H; W = Math.round(H * it.ratio); }
      if (it.cv.width !== W || it.cv.height !== H) { it.cv.width = W; it.cv.height = H; }
      if (!calm) it.mesh.rotation.z -= dt * 0.0004;
      it.cam.aspect = W / H; it.cam.updateProjectionMatrix();
      liveR.setViewport(0, 0, W, H); liveR.setScissor(0, 0, W, H); liveR.setScissorTest(true); liveR.clear(); liveR.render(it.scene, it.cam);
      var cx = it.cv.getContext('2d'); cx.clearRect(0, 0, W, H);                          // clear first: the 3D image has transparent areas
      cx.drawImage(liveR.domElement, 0, BUF_H - H, W, H, 0, 0, W, H);                      // the WebGL buffer's origin is bottom-left
    });
    requestAnimationFrame(frame);
  }
  window.bossView = function (id, ratio, cv) {
    cv._args = [id, ratio];
    var rc = cv.isConnected ? cv.getBoundingClientRect() : null;
    if (rc && rc.width > 0 && rc.bottom > -200 && rc.top < innerHeight + 200) start(id, ratio, cv);      // already on the page and in view: start now (a switch of view), no waiting for the observer
    else startIO.observe(cv);                                                                           // not attached or off screen yet: start when it scrolls into view
  };})();
