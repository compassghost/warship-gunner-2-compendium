/* Smooth water generator built from the game's own sea tiles (see tools/export_water_set.py and notes/water.md).
   The game's sea is two 8-bit indexed tiles per group (A = rough highlight layer, B = soft base layer) that it recolours with one of 16 alternate palettes per group.
   This turns them into a smooth, endless-looking sea: the palette lookup is done in the shader and the colours are filtered AFTER the lookup (no banding, no blocky pixels),
   several scaled / rotated / drifting copies of the base tile are mixed so no repeat shows, a few sine waves move the surface and give it a normal, and the highlight tile adds
   glints and a little bump. What the game does with the tiles (how they move) is NOT known; the motion here is a plausible choice.

   WGWater.load(base)            -> Promise of { groups, tex(group) } (loads water.json, idx_*.png, pal_*.png from `base`, default 'water/')
   WGWater.create(set, opts)     -> { mesh, update(seconds), setOptions(o), dispose() }
   options: group 0-4, row ('own' or palette 0-15), size (world units), tile (world units one base tile covers), waveHeight, waveLength, speed, detail (0-1),
            bump, smooth (true = bilinear after lookup), sun {x,y,z}, fogDensity, fogNear / fogFar (fogFar > 0: linear fog like the game), up ('y' default; 'z' rotates the mesh so z is up)
   Needs THREE (r128). */
(function () {
  var VERT = [
    'uniform float uTime, uWaveH, uWaveL, uSpeed;',
    'varying vec3 vPos; varying vec3 vN; varying vec2 vXZ; varying float vRad;',
    'uniform float uSize;',
    'vec3 wave(vec2 p, vec2 d, float k, float a, float w) {',
    '  float ph = dot(d, p) * k + uTime * uSpeed * w;',
    '  return vec3(a * sin(ph), a * k * d.x * cos(ph), a * k * d.y * cos(ph));',   // height, d/dx, d/dz
    '}',
    'void main() {',
    '  vec2 p = position.xz; float k = 6.2831853 / uWaveL;',
    '  vec3 s = wave(p, normalize(vec2(1.0, 0.35)), k, uWaveH, 1.00)',
    '         + wave(p, normalize(vec2(-0.4, 1.0)), k * 1.7, uWaveH * 0.45, 1.31)',
    '         + wave(p, normalize(vec2(0.8, -0.9)), k * 2.9, uWaveH * 0.22, 1.73)',
    '         + wave(p, normalize(vec2(-1.0, -0.2)), k * 4.3, uWaveH * 0.10, 2.20);',
    '  vec3 pos = vec3(position.x, s.x, position.z);',
    '  vN = normalize(vec3(-s.y, 1.0, -s.z)); vPos = pos; vXZ = p; vRad = length(p) / (uSize * 0.5);',
    '  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);',
    '}'
  ].join('\n');

  var FRAG = [
    'precision highp float;',
    'uniform sampler2D uA, uB, uPal; uniform vec2 uSizeA, uSizeB; uniform float uRowA, uRowB, uTile, uTime, uSpeed, uDetail, uBump, uSmooth, uFogDen, uFogNear, uFogFar;',
    'uniform vec3 uSun, uFog, uSky, uSunCol; uniform float uRows;',
    'varying vec3 vPos; varying vec3 vN; varying vec2 vXZ; varying float vRad;',
    'vec3 palc(float idx, float row) { return texture2D(uPal, vec2((idx * 255.0 + 0.5) / 256.0, (row + 0.5) / uRows)).rgb; }',
    'vec3 tile(sampler2D T, vec2 size, vec2 uv, float row) {',
    '  vec2 p = uv * size - 0.5; vec2 i = floor(p); vec2 f = fract(p);',
    '  f = mix(f, f * f * (3.0 - 2.0 * f), 0.5);',                                   // between linear and smoothstep: soft but not blobby
    '  vec2 a = mod(i, size), b = mod(i + 1.0, size);',
    '  vec3 c00 = palc(texture2D(T, (a + 0.5) / size).r, row);',
    '  vec3 c10 = palc(texture2D(T, (vec2(b.x, a.y) + 0.5) / size).r, row);',
    '  vec3 c01 = palc(texture2D(T, (vec2(a.x, b.y) + 0.5) / size).r, row);',
    '  vec3 c11 = palc(texture2D(T, (b + 0.5) / size).r, row);',
    '  return mix(mix(c00, c10, f.x), mix(c01, c11, f.x), f.y);',
    '}',
    'vec3 tileNearest(sampler2D T, vec2 size, vec2 uv, float row) { vec2 q = floor(uv * size); return palc(texture2D(T, (mod(q, size) + 0.5) / size).r, row); }',
    'vec3 samp(sampler2D T, vec2 size, vec2 uv, float row) { return uSmooth > 0.5 ? tile(T, size, uv, row) : tileNearest(T, size, uv, row); }',
    'vec2 rot(vec2 p, float a) { float c = cos(a), s = sin(a); return vec2(c * p.x - s * p.y, s * p.x + c * p.y); }',
    'float lum(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }',
    'void main() {',
    '  float t = uTime * uSpeed;',
    '  vec2 p = vXZ / uTile;',
    '  vec2 u1 = rot(p, 0.30) + vec2(t * 0.010, t * 0.006);',
    '  vec2 u2 = rot(p, -0.95) / 1.37 + vec2(-t * 0.007, t * 0.009);',
    '  vec2 u3 = rot(p, 2.10) / 2.11 + vec2(t * 0.004, -t * 0.011);',
    '  float w = 0.5 + 0.25 * sin(p.x * 0.7 + p.y * 0.4 + t * 0.05);',                // slowly moving mix weight, so the blend of the copies is not a fixed pattern
    '  vec3 base = mix(samp(uB, uSizeB, u1, uRowB), samp(uB, uSizeB, u2, uRowB), w);',
    '  base = mix(base, samp(uB, uSizeB, u3, uRowB), 0.25);',
    '  vec2 ua = rot(p, 1.20) * 1.9 + vec2(t * 0.020, -t * 0.014); vec2 ua2 = rot(p, -0.40) * 1.3 + vec2(-t * 0.012, -t * 0.009);',
    '  vec3 dA = samp(uA, uSizeA, ua, uRowA); vec3 dA2 = samp(uA, uSizeA, ua2, uRowA); vec3 det = mix(dA, dA2, 0.5);',
    '  float e = 1.0 / 128.0;',
    '  float l0 = lum(dA), lx = lum(samp(uA, uSizeA, ua + vec2(e, 0.0), uRowA)), ly = lum(samp(uA, uSizeA, ua + vec2(0.0, e), uRowA));',
    '  vec3 n = normalize(vN + uBump * vec3(l0 - lx, 0.0, l0 - ly) * 6.0);',
    '  vec3 V = normalize(cameraPosition - vPos); vec3 L = normalize(uSun);',
    '  vec3 col = mix(base, det, uDetail) * (0.85 + 0.45 * lum(det));',
    '  float diff = 0.55 + 0.45 * max(dot(n, L), 0.0);',
    '  vec3 R = reflect(-L, n); float spec = pow(max(dot(R, V), 0.0), 48.0) * (0.35 + 1.4 * lum(det));',
    '  float fres = pow(1.0 - max(dot(n, V), 0.0), 3.0);',
    '  col = col * diff + uSunCol * spec * 0.8;',
    '  col = mix(col, uSky, fres * 0.45);',
    '  float d = length(cameraPosition - vPos); float fog = uFogFar > 0.0 ? (d - uFogNear) / (uFogFar - uFogNear) : 1.0 - exp(-d * uFogDen);',   // linear = the game's GS fog (notes/weather.md)
    '  col = mix(col, uFog, clamp(fog, 0.0, 1.0));',
    '  float edge = 1.0 - smoothstep(0.82, 1.0, vRad);',
    '  gl_FragColor = vec4(col, edge);',
    '}'
  ].join('\n');

  function img(url) { return new Promise(function (res, rej) { var i = new Image(); i.onload = function () { res(i); }; i.onerror = rej; i.src = url; }); }
  function pixels(i) { var c = document.createElement('canvas'); c.width = i.width; c.height = i.height; var x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(i, 0, 0); return x.getImageData(0, 0, i.width, i.height); }
  function dataTex(i, nearest) {                                              // index images: the RED channel is the palette index; must not be filtered or colour-managed
    var d = pixels(i), t = new THREE.DataTexture(new Uint8Array(d.data.buffer.slice(0)), i.width, i.height, THREE.RGBAFormat);
    t.minFilter = t.magFilter = THREE.NearestFilter; t.generateMipmaps = false; t.needsUpdate = true; return t;
  }
  function avgBright(pal, row, top) {                                           // mean of the `top` brightest colours of a palette row (the sea's "sky / fog" tint)
    var cols = []; for (var k = 0; k < 256; k++) { var o = (row * 256 + k) * 4; cols.push([pal.data[o], pal.data[o + 1], pal.data[o + 2]]); }
    cols.sort(function (a, b) { return (a[0] + a[1] + a[2]) - (b[0] + b[1] + b[2]); });
    var s = [0, 0, 0], n = 0; cols.slice(-top).forEach(function (c) { s[0] += c[0]; s[1] += c[1]; s[2] += c[2]; n++; });
    return new THREE.Color(s[0] / n / 255, s[1] / n / 255, s[2] / n / 255);
  }

  window.WGWater = {
    load: async function (base) {
      base = base || 'water/';
      var groups = await (await fetch(base + 'water.json', { cache: 'no-cache' })).json(), set = { groups: groups, g: [] };
      await Promise.all(groups.map(async function (g) {
        var a = await img(base + 'idx_' + g.a.entry + '.png'), b = await img(base + 'idx_' + g.b.entry + '.png'), p = await img(base + 'pal_' + g.id + '.png'), pd = pixels(p);
        var pbytes = new Uint8Array(256 * 19 * 4); pbytes.set(pd.data);                   // row 18 = the game's runtime sea palette (WGWater setGamePalette)
        var pt = new THREE.DataTexture(pbytes, 256, 19, THREE.RGBAFormat); pt.minFilter = pt.magFilter = THREE.NearestFilter; pt.generateMipmaps = false; pt.needsUpdate = true;
        set.g[g.id] = { a: dataTex(a), b: dataTex(b), pal: pt, pd: { data: pbytes }, info: g };
      }));
      return set;
    },
    create: function (set, o) {
      o = Object.assign({ group: 3, row: 'own', size: 400000, segments: 220, tile: 6000, waveHeight: 90, waveLength: 5000, speed: 1, detail: 0.35, bump: 0.6, smooth: true, fogDensity: 0.000012, sun: { x: -0.5, y: 0.75, z: 0.4 }, up: 'y' }, o || {});
      var U = {
        uA: { value: null }, uB: { value: null }, uPal: { value: null }, uSizeA: { value: new THREE.Vector2(128, 128) }, uSizeB: { value: new THREE.Vector2(128, 128) }, uRows: { value: 19 },
        uRowA: { value: 0 }, uRowB: { value: 1 }, uTile: { value: o.tile }, uTime: { value: 0 }, uSpeed: { value: o.speed }, uDetail: { value: o.detail }, uBump: { value: o.bump }, uSmooth: { value: 1 },
        uFogDen: { value: o.fogDensity }, uFogNear: { value: 0 }, uFogFar: { value: 0 }, uSun: { value: new THREE.Vector3() }, uFog: { value: new THREE.Color() }, uSky: { value: new THREE.Color() }, uSunCol: { value: new THREE.Color(1, 0.96, 0.85) },
        uWaveH: { value: o.waveHeight }, uWaveL: { value: o.waveLength }, uSize: { value: o.size }
      };
      var mat = new THREE.ShaderMaterial({ uniforms: U, vertexShader: VERT, fragmentShader: FRAG, transparent: true, side: THREE.DoubleSide, depthWrite: true });
      var geo = new THREE.PlaneGeometry(o.size, o.size, o.segments, o.segments); geo.rotateX(-Math.PI / 2);
      var mesh = new THREE.Mesh(geo, mat); mesh.frustumCulled = false; mesh.renderOrder = -1;
      var holder = new THREE.Group(); holder.add(mesh); if (o.up === 'z') holder.rotation.x = Math.PI / 2;
      function apply() {
        var G = set.g[o.group]; U.uA.value = G.a; U.uB.value = G.b; U.uPal.value = G.pal;
        U.uSizeA.value.set(G.info.a.w, G.info.a.h); U.uSizeB.value.set(G.info.b.w, G.info.b.h);
        if (o.row === 'own') { U.uRowA.value = 0; U.uRowB.value = 1; } else if (o.row === 'game') { U.uRowA.value = U.uRowB.value = 18; } else { U.uRowA.value = U.uRowB.value = 2 + (+o.row); }
        var row = U.uRowB.value; U.uSky.value.copy(avgBright(G.pd, row, 24)); U.uFog.value.copy(avgBright(G.pd, row, 80)).multiplyScalar(0.85);
        U.uSun.value.set(o.sun.x, o.sun.y, o.sun.z).normalize(); U.uTile.value = o.tile; U.uSpeed.value = o.speed; U.uDetail.value = o.detail; U.uBump.value = o.bump; U.uSmooth.value = o.smooth ? 1 : 0;
        U.uWaveH.value = o.waveHeight; U.uWaveL.value = o.waveLength; U.uFogDen.value = o.fogDensity;
        U.uFogNear.value = o.fogNear || 0; U.uFogFar.value = o.fogFar || 0;            // fogFar > 0: linear fog from fogNear to fogFar (the game's GS fog), else the old exp fog
      }
      apply();
      return {
        mesh: holder, options: o, uniforms: U,
        update: function (sec) { U.uTime.value = sec; },
        setOptions: function (n) { Object.assign(o, n); apply(); },
        // The game's own sea palette for one moment: `bgra` = 1024 bytes (256 x B,G,R,A) as in MAP.BIN 16-22 (blended by the game's rule, see notes/weather.md).
        // Applies it to the base and highlight tiles' indices (row 'game'); alpha is ignored here (the game draws the sea semi-transparent).
        setGamePalette: function (bgra) {
          var G = set.g[o.group], d = G.pd.data, b = 18 * 1024;
          for (var k = 0; k < 256; k++) { d[b + 4 * k] = bgra[4 * k + 2]; d[b + 4 * k + 1] = bgra[4 * k + 1]; d[b + 4 * k + 2] = bgra[4 * k]; d[b + 4 * k + 3] = 255; }
          G.pal.needsUpdate = true; o.row = 'game'; apply();
        },
        dispose: function () { geo.dispose(); mat.dispose(); }
      };
    }
  };
})();
