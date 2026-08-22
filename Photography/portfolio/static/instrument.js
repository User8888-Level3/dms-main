/* ═══════════════════════════════════════════════════════════════════════════
   HARV BALU — THE INSTRUMENT (the overture of /work)

   A reflex camera — an EOS body with its kit zoom — drawn in three
   dimensions out of the Observatory's own light: gold hairlines, translucent
   glass, a near-black shell you can see straight through. No framework, no
   WebGL, no model file: the geometry is built here in millimetres, projected
   by a small painter's-algorithm renderer onto a 2D canvas.

   The piece is scroll-driven (the stage is pinned for a tall runway):
     load      the parts arrive out of the dark and lock together
     turn      one full rotation, presented
     explode   the parts separate along the optical axis, labelled
     return    it closes, and the view swings to look into the lens
     enter     the visitor becomes the light — down the optical axis,
               through the glass, the iris opens, the mirror lifts, the
               first curtain drops, the rays converge
     record    the sensor ignites and the photograph blooms out of it
   "Look inside" plays the whole runway; dragging turns the instrument.

   Contract kept: transform/opacity-only DOM writes, pauses off-screen,
   a single still frame under prefers-reduced-motion, no layout thrash.
   Labels are real DOM (Fragment Mono) positioned from projected anchors.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const root = document.querySelector('.instrument');
  if (!root) return;
  const stage = root.querySelector('.instrument-stage');
  const canvas = root.querySelector('.instrument-canvas');
  const labelsEl = root.querySelector('.instrument-labels');
  const photo = root.querySelector('.instrument-photo');
  const photoImg = photo ? photo.querySelector('img') : null;
  const logEl = root.querySelector('[data-instrument-log]');
  const cue = root.querySelector('.instrument-cue');
  const ctx = canvas && canvas.getContext('2d');
  if (!stage || !ctx) return;

  const mqReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const mqCoarse = window.matchMedia('(pointer: coarse)');
  const mqNarrow = window.matchMedia('(max-width: 640px)');

  /* ─── small math ───────────────────────────────────────────────────────── */

  const TAU = Math.PI * 2;
  const RAD = Math.PI / 180;
  const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
  const seg = (p, a, b) => clamp01((p - a) / (b - a));
  const lerp = (a, b, t) => a + (b - a) * t;
  const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  const easeIn = (t) => t * t * t;
  const easeOutExpo = (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));
  const smooth = (t) => t * t * (3 - 2 * t);

  /* deterministic pseudo-random — the scatter must be the same on every load */
  let seed = 20160917;
  const rnd = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };

  /* ─── geometry builders (local coords, millimetres) ────────────────────── */
  /* A part is { verts:[[x,y,z]…], faces:[{v:[i…], m}], edges:[[i,j,m]] }.
     Faces give occlusion and shading; edges are the drawn lines — feature
     edges only, never the triangulation. */

  const mesh = () => ({ verts: [], faces: [], edges: [] });
  const addV = (g, x, y, z) => { g.verts.push([x, y, z]); return g.verts.length - 1; };

  /* Revolve a [r, z] profile around the local Z axis. */
  function lathe(g, profile, segs, m, opts) {
    opts = opts || {};
    const rings = [];
    const base = g.verts.length;
    for (let i = 0; i < profile.length; i++) {
      const r = profile[i][0], z = profile[i][1];
      const ring = [];
      for (let s = 0; s < segs; s++) {
        const a = (s / segs) * TAU;
        ring.push(addV(g, r * Math.cos(a), r * Math.sin(a), z));
      }
      rings.push(ring);
    }
    for (let i = 0; i < rings.length - 1; i++) {
      const ra = profile[i][0], rb = profile[i + 1][0];
      if (ra === 0 && rb === 0) continue;
      for (let s = 0; s < segs; s++) {
        const n = (s + 1) % segs;
        if (ra === 0) g.faces.push({ v: [rings[i][s], rings[i + 1][n], rings[i + 1][s]], m });
        else if (rb === 0) g.faces.push({ v: [rings[i][s], rings[i][n], rings[i + 1][s]], m });
        else g.faces.push({ v: [rings[i][s], rings[i][n], rings[i + 1][n], rings[i + 1][s]], m });
      }
    }
    const em = opts.edgeM || m;
    const ringEvery = opts.rings || null;    // indexes of profile rows that draw a ring
    for (let i = 0; i < rings.length; i++) {
      if (profile[i][0] === 0) continue;
      if (ringEvery && ringEvery.indexOf(i) < 0) continue;
      for (let s = 0; s < segs; s++) g.edges.push([rings[i][s], rings[i][(s + 1) % segs], em]);
    }
    const longs = opts.longs || 0;           // longitudinal lines, evenly spaced
    if (longs) {
      for (let k = 0; k < longs; k++) {
        const s = Math.round((k / longs) * segs) % segs;
        for (let i = 0; i < rings.length - 1; i++) {
          if (profile[i][0] === 0 || profile[i + 1][0] === 0) continue;
          g.edges.push([rings[i][s], rings[i + 1][s], em]);
        }
      }
    }
    void base;
    return g;
  }

  /* Short ribs around a ring — the rubber of a zoom or focus ring. */
  function ribs(g, r, z0, z1, n, m) {
    for (let k = 0; k < n; k++) {
      const a = (k / n) * TAU;
      const x = r * Math.cos(a), y = r * Math.sin(a);
      g.edges.push([addV(g, x, y, z0), addV(g, x, y, z1), m]);
    }
  }

  /* Axis-aligned box centred on (cx,cy,cz). */
  function box(g, cx, cy, cz, w, h, d, m, opts) {
    opts = opts || {};
    const x0 = cx - w / 2, x1 = cx + w / 2;
    const y0 = cy - h / 2, y1 = cy + h / 2;
    const z0 = cz - d / 2, z1 = cz + d / 2;
    const i = [
      addV(g, x0, y0, z1), addV(g, x1, y0, z1), addV(g, x1, y1, z1), addV(g, x0, y1, z1),  // front
      addV(g, x0, y0, z0), addV(g, x1, y0, z0), addV(g, x1, y1, z0), addV(g, x0, y1, z0)   // back
    ];
    if (!opts.noFaces) {
      g.faces.push({ v: [i[0], i[1], i[2], i[3]], m });          // front  +z
      g.faces.push({ v: [i[5], i[4], i[7], i[6]], m });          // back   -z
      g.faces.push({ v: [i[4], i[0], i[3], i[7]], m });          // left   -x
      g.faces.push({ v: [i[1], i[5], i[6], i[2]], m });          // right  +x
      g.faces.push({ v: [i[3], i[2], i[6], i[7]], m });          // top    +y
      g.faces.push({ v: [i[4], i[5], i[1], i[0]], m });          // bottom -y
    }
    const em = opts.edgeM || m;
    const E = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
    E.forEach((e) => g.edges.push([i[e[0]], i[e[1]], em]));
    return i;
  }

  /* A polygon in the XY plane extruded along Z (depth d, centred at cz). */
  function prismXY(g, pts, cz, d, m, opts) {
    opts = opts || {};
    const z0 = cz - d / 2, z1 = cz + d / 2;
    const f = pts.map((p) => addV(g, p[0], p[1], z1));
    const b = pts.map((p) => addV(g, p[0], p[1], z0));
    const n = pts.length;
    if (!opts.noFaces) {
      g.faces.push({ v: f.slice(), m });
      g.faces.push({ v: b.slice().reverse(), m });
      for (let k = 0; k < n; k++) {
        const k2 = (k + 1) % n;
        g.faces.push({ v: [f[k2], f[k], b[k], b[k2]], m });
      }
    }
    const em = opts.edgeM || m;
    for (let k = 0; k < n; k++) {
      const k2 = (k + 1) % n;
      g.edges.push([f[k], f[k2], em]);
      g.edges.push([b[k], b[k2], em]);
      g.edges.push([f[k], b[k], em]);
    }
  }

  /* A single quad; axis 'xy' (facing z), 'xz' (facing y). */
  function quad(g, cx, cy, cz, w, h, axis, m, opts) {
    opts = opts || {};
    let i;
    if (axis === 'xz') {
      i = [addV(g, cx - w / 2, cy, cz + h / 2), addV(g, cx + w / 2, cy, cz + h / 2),
           addV(g, cx + w / 2, cy, cz - h / 2), addV(g, cx - w / 2, cy, cz - h / 2)];
    } else {
      i = [addV(g, cx - w / 2, cy - h / 2, cz), addV(g, cx + w / 2, cy - h / 2, cz),
           addV(g, cx + w / 2, cy + h / 2, cz), addV(g, cx - w / 2, cy + h / 2, cz)];
    }
    if (!opts.noFaces) g.faces.push({ v: i, m });
    const em = opts.edgeM || m;
    for (let k = 0; k < 4; k++) g.edges.push([i[k], i[(k + 1) % 4], em]);
    return i;
  }

  /* A lens element: two spherical-ish surfaces on a rim of edge thickness t.
     sagF / sagB are the surface sags (positive = convex outward). */
  function lensElement(g, r, zc, t, sagF, sagB, segs) {
    /* traced from the back surface's centre, out along the back, up the
       rim, and in along the front — counter-clockwise in the (r, z) half-
       plane, so the revolved faces all point outward. */
    const prof = [];
    const F = zc + t / 2, B = zc - t / 2;
    prof.push([0, B - sagB]);
    prof.push([r * 0.45, B - sagB * 0.80]);
    prof.push([r * 0.80, B - sagB * 0.36]);
    prof.push([r, B]);
    prof.push([r, F]);
    prof.push([r * 0.80, F + sagF * 0.36]);
    prof.push([r * 0.45, F + sagF * 0.80]);
    prof.push([0, F + sagF]);
    lathe(g, prof, segs, 'glass', { rings: [1, 3, 4, 6], edgeM: 'glass' });
  }

  /* ─── the model ────────────────────────────────────────────────────────── */
  /* World: X right (viewer's), Y up, Z toward the subject. The optical axis
     runs along Z at x = AX; the grip is at −X (the subject's left), as on a
     real camera seen from the front. EF flange distance 44 mm: mount face at
     z = 18, sensor at z = −26. */

  const AX = 10;
  const fine = !mqCoarse.matches && window.innerWidth >= 900;
  const SEG_L = fine ? 40 : 26;     // barrels
  const SEG_G = fine ? 32 : 20;     // glass
  const SEG_S = fine ? 24 : 16;     // small cylinders

  const parts = [];
  let order = 0;
  /* pos: world position of the local origin · ex: displacement at full
     explode · scatter: where the part starts before assembly · label: text
     · anchor: local label point · side: which side the label sits · m: the
     default material for shading fills; closed: cull back faces. */
  function part(spec) {
    const g = mesh();
    spec.build(g);
    const p = Object.assign({
      g, pos: [0, 0, 0], ex: [0, 0, 0], closed: false, label: '', anchor: null,
      side: 1, delay: order * 0.055, rot: [0, 0, 0], hinge: [0, 0, 0], off: [0, 0, 0],
      alpha: 1, mobile: true
    }, spec);
    order += 1;
    const a = rnd() * TAU, b = (rnd() - 0.5) * Math.PI;
    const d = 150 + rnd() * 110;
    p.scatter = [Math.cos(a) * Math.cos(b) * d, Math.sin(b) * d * 0.8 + 20, Math.sin(a) * Math.cos(b) * d];
    parts.push(p);
    return p;
  }

  /* body — the ghost shell, a single silhouette prism: shoulders, hump, grip */
  part({
    id: 'body', m: 'shell', label: '', ex: [0, 0, 0],
    build(g) {
      const sil = [[-45, -46], [-45, 36], [-30, 40], [-14, 40], [-10, 44], [-2, 62],
                   [22, 62], [30, 44], [34, 40], [54, 40], [67, 30], [67, -46]];
      prismXY(g, sil, -14, 56, 'shell', { noFaces: true });
      /* faint panel lines: the front plate seam and the base plate */
      g.edges.push([addV(g, -45, -38, 14), addV(g, 67, -38, 14), 'shellDim']);
      g.edges.push([addV(g, -45, -38, -42), addV(g, 67, -38, -42), 'shellDim']);
    }
  });
  part({
    id: 'grip', m: 'shell', label: '', ex: [-44, 0, 0], anchor: [-60, -6, 36], side: -1, mobile: false,
    build(g) {
      const sil = [[-66, -48], [-66, 30], [-58, 36], [-44, 36], [-44, -48]];
      prismXY(g, sil, -3, 78, 'shell', { noFaces: true });
    }
  });
  /* mirror box: two walls and a floor, the dark inside of the instrument */
  part({
    id: 'mirrorbox', m: 'dark', ex: [0, 0, 0],
    build(g) {
      const z0 = -22, z1 = 12, y0 = -20, y1 = 20;
      const L = AX - 22, R = AX + 22;
      const a = [addV(g, L, y0, z1), addV(g, L, y1, z1), addV(g, L, y1, z0), addV(g, L, y0, z0)];
      const b = [addV(g, R, y0, z1), addV(g, R, y1, z1), addV(g, R, y1, z0), addV(g, R, y0, z0)];
      g.faces.push({ v: a, m: 'dark' }); g.faces.push({ v: b, m: 'dark' });
      for (let k = 0; k < 4; k++) { g.edges.push([a[k], a[(k + 1) % 4], 'dark']); g.edges.push([b[k], b[(k + 1) % 4], 'dark']); }
      quad(g, AX, y0, -5, 44, 34, 'xz', 'dark');           // floor
      /* the AF module under the floor */
      box(g, AX, -25, -6, 16, 8, 14, 'metal');
    }
  });
  /* the reflex mirror — hinged at its top rear edge; lifts about local X */
  part({
    id: 'mirror', m: 'mirror', label: 'Reflex mirror', anchor: [0, -14, 14], side: -1,
    pos: [AX, 14, -20], ex: [0, 0, 0], hinge: [0, 0, 0],
    build(g) {
      const L = 38, c = Math.SQRT1_2 * L;
      const i = [addV(g, -18, 0, 0), addV(g, 18, 0, 0), addV(g, 18, -c, c), addV(g, -18, -c, c)];
      g.faces.push({ v: i, m: 'mirror' });
      for (let k = 0; k < 4; k++) g.edges.push([i[k], i[(k + 1) % 4], 'mirror']);
      /* sub-mirror: hangs behind, sends light down to the AF module */
      const s = [addV(g, -9, -c * 0.55, c * 0.55), addV(g, 9, -c * 0.55, c * 0.55),
                 addV(g, 9, -c * 0.55 - 9, c * 0.55 - 9), addV(g, -9, -c * 0.55 - 9, c * 0.55 - 9)];
      g.faces.push({ v: s, m: 'mirrorDim' });
      for (let k = 0; k < 4; k++) g.edges.push([s[k], s[(k + 1) % 4], 'mirrorDim']);
    }
  });
  part({
    id: 'screen', m: 'glassMatte', label: 'Focusing screen', anchor: [-16, 0, 0], side: -1, mobile: false,
    pos: [AX, 21, -6], ex: [0, 30, 0],
    build(g) { quad(g, 0, 0, 0, 32, 22, 'xz', 'glassMatte'); }
  });
  part({
    id: 'penta', m: 'glass', label: 'Pentamirror', anchor: [0, 24, 0], side: 1,
    pos: [AX, 24, -8], ex: [0, 58, 0], closed: true,
    build(g) {
      const poly = [[-15, 0], [15, 0], [15, 10], [4, 24], [-4, 24], [-15, 10]];
      prismXY(g, poly, 0, 28, 'glass');
    }
  });
  part({
    id: 'eyepiece', m: 'dark', label: 'Eyepiece', anchor: [0, 8, -4], side: 1, mobile: false,
    pos: [AX, 34, -45], ex: [0, 12, -40], closed: true,
    build(g) {
      lathe(g, [[5, 0], [9, 0], [9, 7], [6, 7], [6, 1], [5, 1]], SEG_S, 'dark', { longs: 0 });
      /* the rubber cup */
      box(g, 0, 0, 9, 24, 18, 3, 'dark');
    }
  });
  /* shutter: a frame and two curtains that travel down */
  part({
    id: 'shutter', m: 'blade', label: 'Shutter · two curtains', anchor: [-16, 14, 0], side: -1,
    pos: [AX, 0, -22], ex: [0, 0, -26],
    build(g) {
      // frame
      quad(g, 0, 14, 0, 44, 6, 'xy', 'dark'); quad(g, 0, -14, 0, 44, 6, 'xy', 'dark');
      quad(g, -19, 0, 0, 6, 22, 'xy', 'dark'); quad(g, 19, 0, 0, 6, 22, 'xy', 'dark');
    }
  });
  const curtain = (id, y0, delayBias) => part({
    id, m: 'blade', label: '', pos: [AX, y0, -22.6], ex: [0, 0, -26], delay: delayBias,
    build(g) {
      quad(g, 0, 0, 0, 28, 19, 'xy', 'blade');
      /* three overlapping blades */
      g.edges.push([addV(g, -14, 3.2, 0.1), addV(g, 14, 3.2, 0.1), 'bladeDim']);
      g.edges.push([addV(g, -14, -3.2, 0.1), addV(g, 14, -3.2, 0.1), 'bladeDim']);
    }
  });
  const curtain1 = curtain('curtain1', 0, 0.5);
  const curtain2 = curtain('curtain2', 19.4, 0.52);
  /* the sensor stack — low-pass glass, the CMOS, its frame */
  part({
    id: 'sensor', m: 'sensor', label: 'CMOS sensor · APS-C', anchor: [12, 8, 0], side: 1,
    pos: [AX, 0, -26], ex: [0, 0, -54],
    build(g) {
      box(g, 0, 0, -2.2, 30, 22, 2.4, 'metal');                  // carrier
      quad(g, 0, 0, 0, 22.3, 14.9, 'xy', 'sensor');              // the CMOS
      for (let k = 1; k < 6; k++) {                              // the pixel grid, sparse
        const x = -11.15 + (22.3 / 6) * k;
        g.edges.push([addV(g, x, -7.45, 0.05), addV(g, x, 7.45, 0.05), 'grid']);
      }
      for (let k = 1; k < 4; k++) {
        const y = -7.45 + (14.9 / 4) * k;
        g.edges.push([addV(g, -11.15, y, 0.05), addV(g, 11.15, y, 0.05), 'grid']);
      }
      quad(g, 0, 0, 1.6, 24, 16.4, 'xy', 'glassMatte');           // low-pass filter
    }
  });
  part({
    id: 'board', m: 'pcb', label: 'Main board', anchor: [-30, 22, 0], side: -1,
    pos: [AX + 2, -2, -34], ex: [0, 0, -86],
    build(g) {
      quad(g, 0, 0, 0, 72, 60, 'xy', 'pcb');
      box(g, -8, 6, -1.6, 12, 12, 2.2, 'chip');                  // the image processor
      box(g, 14, -14, -1.4, 8, 10, 1.8, 'chip');
      box(g, -22, -16, -1.2, 14, 6, 1.4, 'chip');
      /* traces */
      const tr = (pts) => { for (let k = 0; k < pts.length - 1; k++) g.edges.push([addV(g, pts[k][0], pts[k][1], -0.1), addV(g, pts[k + 1][0], pts[k + 1][1], -0.1), 'trace']); };
      tr([[-14, 6], [-26, 6], [-26, 20], [-32, 20]]);
      tr([[-8, 12], [-8, 22], [10, 22], [10, 27]]);
      tr([[-2, 6], [6, 6], [6, -8], [10, -8]]);
      tr([[18, -14], [30, -14], [30, -24]]);
      tr([[-15, -16], [-15, -26], [2, -26]]);
      tr([[22, 4], [22, 16], [34, 16]]);
    }
  });
  part({
    id: 'lcd', m: 'lcd', label: 'Vari-angle LCD', anchor: [34, 20, 0], side: 1,
    pos: [AX, -4, -43.5], ex: [0, 0, -124], closed: true,
    build(g) {
      box(g, 0, 0, 0, 72, 50, 3, 'dark');
      quad(g, 0, 0, -1.6, 66, 44, 'xy', 'lcd');
    }
  });
  part({
    id: 'battery', m: 'metal', label: 'Battery', anchor: [0, -18, 0], side: -1, mobile: false,
    pos: [-55, -12, 8], ex: [0, -64, 0], closed: true,
    build(g) { box(g, 0, 0, 0, 18, 36, 12, 'metal'); }
  });
  /* the top deck: mode dial, release, hot shoe */
  part({
    id: 'dial', m: 'metal', label: 'Mode dial', anchor: [0, 6, 0], side: -1, mobile: false,
    pos: [-50, 40, -10], ex: [0, 44, 0], closed: true,
    build(g) {
      /* the dial's axis is Y: build along Z then rotate verts into Y */
      const t = mesh();
      lathe(t, [[0, 0], [12, 0], [12, 6], [10.5, 6], [10.5, 7], [0, 7]], SEG_S, 'metal', { rings: [1, 2, 3, 4], longs: 0 });
      for (let k = 0; k < 12; k++) {                              // click marks
        const a = (k / 12) * TAU;
        t.edges.push([addV(t, 8 * Math.cos(a), 8 * Math.sin(a), 7.05), addV(t, 11 * Math.cos(a), 11 * Math.sin(a), 7.05), 'metalDim']);
      }
      ribs(t, 12.05, 0.5, 5.5, 24, 'metalDim');                // knurling
      t.verts.forEach((v) => g.verts.push([v[0], v[2], -v[1]]));  // z→y (up), y→−z
      t.faces.forEach((f) => g.faces.push(f)); t.edges.forEach((e) => g.edges.push(e));
    }
  });
  part({
    id: 'release', m: 'metal', label: '', pos: [-55, 36, 26], ex: [0, 26, 0], closed: true, mobile: false,
    build(g) {
      const t = mesh();
      lathe(t, [[0, 0], [5.5, 0], [5.5, 3], [0, 3.4]], SEG_S, 'metal', { rings: [1, 2], longs: 0 });
      t.verts.forEach((v) => g.verts.push([v[0], v[2], -v[1]]));
      t.faces.forEach((f) => g.faces.push(f)); t.edges.forEach((e) => g.edges.push(e));
    }
  });
  part({
    id: 'shoe', m: 'metal', label: 'Hot shoe', anchor: [0, 3, 0], side: 1, mobile: false,
    pos: [AX, 63.5, -4], ex: [0, 84, 0], closed: true,
    build(g) {
      box(g, 0, 0, 0, 20, 3, 22, 'metal');
      box(g, -8, 1.8, 0, 4, 1, 22, 'metal'); box(g, 8, 1.8, 0, 4, 1, 22, 'metal');   // rails
      g.edges.push([addV(g, 0, 1.6, 6), addV(g, 0, 1.6, -6), 'contactDim']);          // centre contact line
    }
  });
  /* the body's mount ring with its contacts and index */
  part({
    id: 'bmount', m: 'metal', label: 'Lens mount', anchor: [0, 34, 0], side: 1, mobile: false,
    pos: [AX, 0, 14], ex: [0, 0, 4], closed: true,
    build(g) {
      lathe(g, [[27, 0], [34, 0], [34, 4], [27, 4]], SEG_L, 'metal', { rings: [0, 1, 2, 3], longs: 0 });
      /* three bayonet lugs inside the throat */
      for (let k = 0; k < 3; k++) {
        const a0 = (k / 3) * TAU + 0.35, a1 = a0 + 0.9;
        const pts = [];
        for (let s = 0; s <= 6; s++) { const a = lerp(a0, a1, s / 6); pts.push([27 * Math.cos(a), 27 * Math.sin(a)]); }
        for (let s = 6; s >= 0; s--) { const a = lerp(a0, a1, s / 6); pts.push([23.5 * Math.cos(a), 23.5 * Math.sin(a)]); }
        prismXY(g, pts, 3.2, 1.4, 'metal', { noFaces: false });
      }
      /* eight gold contacts on the lower arc, and the index mark on top */
      for (let k = 0; k < 8; k++) {
        const a = -Math.PI / 2 + (k - 3.5) * 0.1;
        const x = 29.5 * Math.cos(a), y = 29.5 * Math.sin(a);
        const c = [addV(g, x - 0.9, y, 4.1), addV(g, x + 0.9, y, 4.1), addV(g, x + 0.9, y + 2.4, 4.1), addV(g, x - 0.9, y + 2.4, 4.1)];
        g.faces.push({ v: c, m: 'contact' });
      }
      const ix = [addV(g, -1.2, 34.2, 4.2), addV(g, 1.2, 34.2, 4.2), addV(g, 1.2, 36.8, 4.2), addV(g, -1.2, 36.8, 4.2)];
      g.faces.push({ v: ix, m: 'contact' });
    }
  });
  /* ── the lens ── */
  part({
    id: 'lmount', m: 'metal', label: '', pos: [AX, 0, 18], ex: [0, 0, 10], closed: true,
    build(g) { lathe(g, [[25, 0], [32, 0], [32, 5], [25, 5]], SEG_L, 'metal', { rings: [0, 1, 2, 3], longs: 0 }); }
  });
  part({
    id: 'rear', m: 'glass', label: 'Rear group', anchor: [0, 15, 6], side: -1,
    pos: [AX, 0, 0], ex: [0, 0, 22], closed: false,
    build(g) {
      lensElement(g, 13, 27, 2.4, 1.6, 1.0, SEG_G);
      lensElement(g, 15, 33.5, 2.0, 2.2, -0.6, SEG_G);
    }
  });
  const iris = part({
    id: 'iris', m: 'dark', label: 'Iris · 7 blades', anchor: [0, 21, 2], side: 1,
    pos: [AX, 0, 41], ex: [0, 0, 38], closed: true,
    build(g) { lathe(g, [[17.5, 0], [21.5, 0], [21.5, 4], [17.5, 4]], SEG_G, 'dark', { rings: [0, 1, 2, 3], longs: 0 }); }
  });
  part({
    id: 'mid', m: 'glass', label: '', pos: [AX, 0, 0], ex: [0, 0, 52], closed: false,
    build(g) {
      lensElement(g, 17, 56, 3.0, 2.6, 1.4, SEG_G);
      lensElement(g, 18, 64, 2.6, -1.0, 2.2, SEG_G);
    }
  });
  part({
    id: 'barrel', m: 'shell', label: 'Zoom barrel', anchor: [0, 34, 56], side: 1,
    pos: [AX, 0, 0], ex: [0, 0, 34],
    build(g) {
      lathe(g, [[31, 18], [34, 22], [34, 46], [35, 48], [35, 62], [34, 64], [34, 70], [35, 71], [35, 77], [34, 78], [34, 88], [31, 88], [31, 92]],
        SEG_L, 'shell', { longs: 0 });
      ribs(g, 35.05, 49, 61, fine ? 36 : 20, 'shellDim');         // zoom ring rubber
      ribs(g, 35.05, 72, 76, fine ? 36 : 20, 'shellDim');         // focus ring
    }
  });
  part({
    id: 'inner', m: 'shell', label: '', pos: [AX, 0, 0], ex: [0, 0, 70], mobile: false,
    build(g) {
      lathe(g, [[27, 88], [28.5, 90], [28.5, 106], [30, 108], [30, 112], [26.5, 112], [26.5, 110]], SEG_L, 'shell', { longs: 0 });
    }
  });
  part({
    id: 'front', m: 'glass', label: 'Front element', anchor: [0, 25, 100], side: -1,
    pos: [AX, 0, 0], ex: [0, 0, 96], closed: false,
    build(g) {
      lensElement(g, 23, 93, 2.6, 1.2, 2.4, SEG_G);
      lensElement(g, 25, 101, 4.0, 4.2, 1.6, SEG_G);
    }
  });

  /* materials: fill (rgb, alpha) and line (rgb, alpha). The shell has no
     fill at all — a ghost you see straight through. */
  const GOLD = '212,175,55', HEAT = '238,214,136', STAR = '242,237,224';
  const MAT = {
    shell:      { fill: null, line: GOLD, la: 0.34, lw: 0.85 },
    shellDim:   { fill: null, line: GOLD, la: 0.18, lw: 0.75 },
    metal:      { fill: [8, 8, 7, 16, 15, 12], fa: 0.95, line: GOLD, la: 0.72, lw: 1 },
    metalDim:   { fill: null, line: GOLD, la: 0.34, lw: 0.8 },
    dark:       { fill: [6, 6, 5, 10, 9, 7], fa: 0.96, line: GOLD, la: 0.55, lw: 0.9 },
    blade:      { fill: [8, 8, 7, 13, 12, 9], fa: 0.97, line: GOLD, la: 0.66, lw: 0.9 },
    bladeDim:   { fill: null, line: GOLD, la: 0.28, lw: 0.8 },
    pcb:        { fill: [8, 9, 7, 14, 16, 11], fa: 0.95, line: GOLD, la: 0.5, lw: 0.9 },
    chip:       { fill: [7, 7, 6, 12, 11, 9], fa: 0.97, line: GOLD, la: 0.45, lw: 0.8 },
    trace:      { fill: null, line: GOLD, la: 0.38, lw: 0.8 },
    lcd:        { fill: [7, 8, 8, 11, 13, 14], fa: 0.9, line: STAR, la: 0.35, lw: 0.8 },
    glass:      { fill: 'glass', line: STAR, la: 0.46, lw: 0.9 },
    glassMatte: { fill: 'glassMatte', line: STAR, la: 0.42, lw: 0.85 },
    mirror:     { fill: 'mirror', line: STAR, la: 0.7, lw: 1 },
    mirrorDim:  { fill: 'mirrorDim', line: STAR, la: 0.45, lw: 0.85 },
    sensor:     { fill: 'sensor', line: GOLD, la: 0.95, lw: 1 },
    grid:       { fill: null, line: GOLD, la: 0.4, lw: 0.75 },
    contact:    { fill: 'contact', line: GOLD, la: 0, lw: 0 },
    contactDim: { fill: null, line: GOLD, la: 0.5, lw: 0.8 }
  };

  /* ─── state, camera, choreography ──────────────────────────────────────── */

  let W = 1, H = 1, dpr = 1, focal = 600;
  let p = 0;                       // runway progress 0..1
  let t0 = 0, now = 0;             // seconds since start
  let visible = true, tabShown = !document.hidden, onScreen = true;
  let dragYaw = 0, dragPitch = 0, dragging = false, dragX = 0, dragY = 0, dragVY = 0;
  let runwayTop = 0, runwayLen = 1;
  let labelDom = [];
  let photoBox = { fw: 1, fh: 1 };
  let phaseName = '';
  let lastFrameAt = 0;

  const NEAR = 1.6;
  const MODEL_CENTER = [AX, 4, 18];

  const cam = { yaw: 0, pitch: 0, T: [AX, 4, 18], D: 270 };
  const S = {   // the scene state the choreography writes every frame
    assemble: 0, explode: 0, label: 0, irisOpen: 0.42, mirrorUp: 0, c1: 0, c2: 0,
    rays: 0, ignite: 0, photoT: 0, photoA: 0, canvasA: 1, cueA: 1, headA: 1, epochA: 0,
    entered: 0
  };

  /* keyframes along the runway (progress 0..1) */
  const K = {
    turn0: 0.0, turn1: 0.22,
    exp0: 0.22, exp1: 0.40, hold1: 0.50,
    ret0: 0.50, ret1: 0.60,
    swing0: 0.51, swing1: 0.61,
    dolly0: 0.60, dolly1: 0.67,
    in0: 0.67, in1: 0.86,
    iris0: 0.70, iris1: 0.76,
    mir0: 0.75, mir1: 0.80,
    c1a: 0.80, c1b: 0.845,
    ray0: 0.71, ray1: 0.87,
    ign0: 0.82, ign1: 0.885,
    ph0: 0.88, ph1: 0.96,
    c2a: 0.975, c2b: 0.995
  };

  const YAW0 = 34, PITCH0 = 11;

  function choreograph() {
    let yaw, pitch, T, D;
    const ambientAmp = 1 - seg(p, 0, 0.06);
    const amb = ambientAmp * (mqReduce.matches ? 0 : 1);
    const ambYaw = 9 * Math.sin(now / 7.2) * amb;
    const ambPitch = 2.2 * Math.sin(now / 5.1 + 1) * amb;
    const ambLift = 2.2 * Math.sin(now / 4.3) * amb;

    const tTurn = easeInOut(seg(p, K.turn0, K.turn1));
    const tExpDrift = seg(p, K.exp0, K.hold1);
    const tSwing = easeInOut(seg(p, K.swing0, K.swing1));

    yaw = YAW0 + 360 * tTurn - 22 * tExpDrift;
    pitch = PITCH0 + 7 * tTurn + 6 * tExpDrift;
    /* swing to the front, looking down the axis */
    yaw = lerp(yaw, 0, tSwing);
    pitch = lerp(pitch, 0, tSwing);
    yaw += ambYaw + dragYaw * (1 - tSwing);
    pitch += ambPitch + dragPitch * (1 - tSwing);

    /* the swing orbits the eye round to the front at full distance (never
       through the body); the dolly then runs it down the axis to the glass;
       the travel carries it on through the lens into the box */
    const tDolly = easeInOut(seg(p, K.dolly0, K.dolly1));
    const tIn = easeInOut(seg(p, K.in0, K.in1));
    const T34 = [MODEL_CENTER[0], MODEL_CENTER[1] + ambLift, MODEL_CENTER[2] + 18 * tExpDrift];
    const Taxis = [AX, 0, 18];
    /* the exploded view is wider — back off a little to hold it */
    const D34 = 270 + 70 * easeInOut(seg(p, K.exp0, K.exp1)) - 70 * easeInOut(seg(p, K.ret0, K.ret1));
    T = [lerp(T34[0], Taxis[0], tSwing), lerp(T34[1], Taxis[1], tSwing), lerp(T34[2], Taxis[2], tSwing)];
    D = D34 + (mqReduce.matches ? 70 : 0);
    if (tDolly > 0) {
      /* eye z: 288 (front, far) → 158 (at the glass) → 9 (inside the box) */
      const eyeZ = tIn > 0 ? lerp(158, 9, tIn) : lerp(Taxis[2] + D34, 158, tDolly);
      D = lerp(D34, 40, tDolly);
      T = [AX, 0, eyeZ - D];
    }

    cam.yaw = yaw * RAD; cam.pitch = pitch * RAD; cam.T = T; cam.D = D;
    S.swing = tSwing;

    S.explode = easeInOut(seg(p, K.exp0, K.exp1)) * (1 - easeInOut(seg(p, K.ret0, K.ret1)));
    S.label = seg(p, 0.27, 0.36) * (1 - seg(p, K.hold1 - 0.02, K.ret0 + 0.04));
    S.irisOpen = lerp(0.42, 1, easeInOut(seg(p, K.iris0, K.iris1)));
    S.mirrorUp = easeInOut(seg(p, K.mir0, K.mir1));
    S.c1 = easeInOut(seg(p, K.c1a, K.c1b));
    S.c2 = easeInOut(seg(p, K.c2a, K.c2b));
    S.rays = seg(p, K.ray0, K.ray1);
    S.ignite = easeOut(seg(p, K.ign0, K.ign1));
    S.photoT = easeInOut(seg(p, K.ph0, K.ph1));
    S.photoA = easeOut(seg(p, K.ph0 - 0.015, K.ph0 + 0.045));
    S.canvasA = 1 - easeIn(seg(p, 0.915, 0.985));
    S.cueA = 1 - seg(p, 0.0, 0.04);
    S.headA = (1 - 0.65 * S.label) * (1 - seg(p, 0.50, 0.62));
    S.epochA = seg(p, 0.97, 1.0);
    S.entered = tIn;

    /* the log line — an instrument readout */
    let ph;
    if (p < 0.02) ph = 'Assembled · EOS reflex body · 18–55 zoom';
    else if (p < K.exp0) ph = 'Presented · one rotation';
    else if (p < K.ret0) ph = 'Exploded view · sixteen parts';
    else if (p < K.in0) ph = 'Closed · on the optical axis';
    else if (p < K.iris0) ph = 'Entering the optical path';
    else if (p < K.mir0) ph = 'Iris opening · f/3.5';
    else if (p < K.c1a) ph = 'Mirror up';
    else if (p < K.ign0) ph = 'First curtain';
    else if (p < K.ph0) ph = 'Exposure';
    else ph = 'Observation recorded';
    if (ph !== phaseName && logEl) { phaseName = ph; logEl.textContent = ph; }
  }

  /* ─── projection ───────────────────────────────────────────────────────── */

  let cy_ = 1, sy_ = 0, cp_ = 1, sp_ = 0, cxS = 0, cyS = 0;
  function beginView() {
    cy_ = Math.cos(cam.yaw); sy_ = Math.sin(cam.yaw);
    cp_ = Math.cos(cam.pitch); sp_ = Math.sin(cam.pitch);
    cxS = W / 2; cyS = H / 2;
  }
  /* world → view (x, y, depth), depth > 0 is in front of the eye */
  function toView(w) {
    const px = w[0] - cam.T[0], py = w[1] - cam.T[1], pz = w[2] - cam.T[2];
    const x1 = px * cy_ + pz * sy_;
    const z1 = -px * sy_ + pz * cy_;
    const y2 = py * cp_ - z1 * sp_;
    const z2 = py * sp_ + z1 * cp_;
    return [x1, y2, cam.D - z2];
  }
  const proj = (v) => [cxS + focal * v[0] / v[2], cyS - focal * v[1] / v[2]];

  /* clip a polygon (view coords) against depth = NEAR */
  function clipPoly(pts) {
    let out = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i + 1) % pts.length];
      const ain = a[2] > NEAR, bin = b[2] > NEAR;
      if (ain) out.push(a);
      if (ain !== bin) {
        const t = (NEAR - a[2]) / (b[2] - a[2]);
        out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, NEAR]);
      }
    }
    return out;
  }
  function clipSeg(a, b) {
    const ain = a[2] > NEAR, bin = b[2] > NEAR;
    if (ain && bin) return [a, b];
    if (!ain && !bin) return null;
    const t = (NEAR - a[2]) / (b[2] - a[2]);
    const m = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, NEAR];
    return ain ? [a, m] : [m, b];
  }

  /* per-part world transform: rotate about a local hinge, then place */
  function placePart(pt, v) {
    let x = v[0] - pt.hinge[0], y = v[1] - pt.hinge[1], z = v[2] - pt.hinge[2];
    const rx = pt.rot[0];
    if (rx) { const c = Math.cos(rx), s = Math.sin(rx); const y1 = y * c - z * s; z = y * s + z * c; y = y1; }
    x += pt.hinge[0]; y += pt.hinge[1]; z += pt.hinge[2];
    const e = S.explode, k = 1 - pt.arrive;
    return [
      x + pt.pos[0] + pt.ex[0] * e + pt.scatter[0] * k + pt.off[0],
      y + pt.pos[1] + pt.ex[1] * e + pt.scatter[1] * k + pt.off[1],
      z + pt.pos[2] + pt.ex[2] * e + pt.scatter[2] * k + pt.off[2]
    ];
  }

  /* ─── rendering ────────────────────────────────────────────────────────── */

  const items = [];   // { d, kind, pts, m, n?, a }
  const LIGHT = (() => { const l = [-0.42, 0.62, 0.66]; const n = Math.hypot(l[0], l[1], l[2]); return [l[0] / n, l[1] / n, l[2] / n]; })();

  function fillFor(m, lam, spec, a) {
    const M = MAT[m];
    const f = M.fill;
    if (!f) return null;
    if (f === 'glass') {
      const al = (0.018 + 0.03 * lam + 0.26 * spec) * a;
      return 'rgba(' + STAR + ',' + al.toFixed(3) + ')';
    }
    if (f === 'glassMatte') return 'rgba(' + STAR + ',' + ((0.035 + 0.04 * lam) * a).toFixed(3) + ')';
    if (f === 'mirror') return 'rgba(' + STAR + ',' + ((0.05 + 0.08 * lam + 0.22 * spec) * a).toFixed(3) + ')';
    if (f === 'mirrorDim') return 'rgba(' + STAR + ',' + ((0.04 + 0.07 * lam) * a).toFixed(3) + ')';
    if (f === 'sensor') {
      const g = S.ignite;
      const al = (0.1 + 0.12 * lam + 0.62 * g) * a;
      return 'rgba(' + (g > 0.5 ? HEAT : GOLD) + ',' + al.toFixed(3) + ')';
    }
    if (f === 'contact') return 'rgba(' + GOLD + ',' + (0.85 * a).toFixed(3) + ')';
    const r = Math.round(f[0] + (f[3] - f[0]) * lam);
    const gg = Math.round(f[1] + (f[4] - f[1]) * lam);
    const b = Math.round(f[2] + (f[5] - f[2]) * lam);
    return 'rgba(' + r + ',' + gg + ',' + b + ',' + (M.fa * a).toFixed(3) + ')';
  }

  function render() {
    ctx.clearRect(0, 0, W, H);
    if (S.canvasA <= 0.002) return;
    ctx.globalAlpha = S.canvasA;
    beginView();
    items.length = 0;

    let dMin = Infinity, dMax = -Infinity;
    const anchors = [];

    for (let pi = 0; pi < parts.length; pi++) {
      const pt = parts[pi];
      if (pt.alpha <= 0.003) continue;
      const g = pt.g;
      const vv = new Array(g.verts.length);
      let anyNear = false, allBehind = true;
      for (let i = 0; i < g.verts.length; i++) {
        const v = toView(placePart(pt, g.verts[i]));
        vv[i] = v;
        if (v[2] > NEAR) allBehind = false;
        if (v[2] < NEAR + 60) anyNear = true;
      }
      if (allBehind) continue;
      /* the part is fading as the eye passes through it */
      let passA = 1;
      if (anyNear) {
        let cz = 0; for (let i = 0; i < vv.length; i++) cz += vv[i][2]; cz /= vv.length;
        passA = clamp01((cz - NEAR) / 18);
      }
      const pa = pt.alpha * passA;
      if (pa <= 0.003) continue;

      /* faces */
      for (let fi = 0; fi < g.faces.length; fi++) {
        const f = g.faces[fi];
        const M = MAT[f.m];
        if (!M.fill) continue;
        let pts = f.v.map((ix) => vv[ix]);
        /* normal from the first three points (view space) */
        const a0 = pts[0], a1 = pts[1], a2 = pts[2];
        const ux = a1[0] - a0[0], uy = a1[1] - a0[1], uz = -(a1[2] - a0[2]);
        const wx = a2[0] - a0[0], wy = a2[1] - a0[1], wz = -(a2[2] - a0[2]);
        let nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx;
        const nl = Math.hypot(nx, ny, nz) || 1;
        nx /= nl; ny /= nl; nz /= nl;
        /* facing: view dir is +z toward the eye in this frame (eye at +depth) */
        if (pt.closed && nz < 0) continue;
        let lam = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2];
        if (!pt.closed) lam = Math.abs(lam); else lam = Math.max(0, lam);
        /* specular toward the eye */
        const rz = 2 * lam * nz - LIGHT[2];
        const spec = Math.pow(Math.max(0, rz), 28);
        pts = clipPoly(pts);
        if (pts.length < 3) continue;
        let d = 0; for (let i = 0; i < pts.length; i++) d += pts[i][2]; d /= pts.length;
        if (d < dMin) dMin = d; if (d > dMax) dMax = d;
        items.push({ d, kind: 0, pts: pts.map(proj), fill: fillFor(f.m, lam, spec, pa), m: f.m, a: pa });
      }
      /* edges */
      for (let ei = 0; ei < g.edges.length; ei++) {
        const e = g.edges[ei];
        const s = clipSeg(vv[e[0]], vv[e[1]]);
        if (!s) continue;
        const d = (s[0][2] + s[1][2]) / 2;
        if (d < dMin) dMin = d; if (d > dMax) dMax = d;
        items.push({ d, kind: 1, pts: [proj(s[0]), proj(s[1])], m: e[2], a: pa });
      }
      /* label anchor */
      if (pt.label && pt.anchor && S.label > 0.001) {
        const v = toView(placePart(pt, pt.anchor));
        if (v[2] > NEAR) anchors.push({ pt, s: proj(v), d: v[2] });
      }
    }

    /* the iris blades are built every frame — they move */
    drawIrisBlades(dMin, dMax);

    /* the light: rays converging through the glass onto the sensor */
    if (S.rays > 0.001) drawRays();

    const span = Math.max(1, dMax - dMin);
    const fog = (d) => 1 - 0.62 * clamp01((d - dMin) / span);

    items.sort((a, b) => b.d - a.d);

    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const fg = fog(it.d);
      if (it.kind === 0) {
        const pts = it.pts;
        ctx.beginPath();
        ctx.moveTo(pts[0][0], pts[0][1]);
        for (let k = 1; k < pts.length; k++) ctx.lineTo(pts[k][0], pts[k][1]);
        ctx.closePath();
        ctx.fillStyle = it.fill;
        ctx.fill();
      } else if (it.kind === 1) {
        const M = MAT[it.m];
        const al = M.la * it.a * fg;
        if (al < 0.01) continue;
        ctx.strokeStyle = 'rgba(' + M.line + ',' + al.toFixed(3) + ')';
        ctx.lineWidth = M.lw;
        ctx.beginPath();
        ctx.moveTo(it.pts[0][0], it.pts[0][1]);
        ctx.lineTo(it.pts[1][0], it.pts[1][1]);
        ctx.stroke();
      } else if (it.kind === 2) {
        /* a ray: soft wide pass under a fine bright line */
        const pts = it.pts;
        ctx.beginPath();
        ctx.moveTo(pts[0][0], pts[0][1]);
        for (let k = 1; k < pts.length; k++) ctx.lineTo(pts[k][0], pts[k][1]);
        ctx.strokeStyle = 'rgba(' + HEAT + ',' + (0.07 * it.a).toFixed(3) + ')';
        ctx.lineWidth = 7;
        ctx.stroke();
        ctx.strokeStyle = 'rgba(' + HEAT + ',' + (0.55 * it.a).toFixed(3) + ')';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }

    /* the sensor's glow when it ignites — drawn last, light over everything */
    if (S.ignite > 0.002) {
      const sc = sensorScreen();
      if (sc) {
        const rr = Math.max(sc.w, sc.h) * (0.9 + 0.9 * S.ignite);
        const gr = ctx.createRadialGradient(sc.x, sc.y, 0, sc.x, sc.y, rr);
        gr.addColorStop(0, 'rgba(' + HEAT + ',' + (0.42 * S.ignite * (1 - S.photoT)).toFixed(3) + ')');
        gr.addColorStop(0.35, 'rgba(' + GOLD + ',' + (0.16 * S.ignite * (1 - S.photoT)).toFixed(3) + ')');
        gr.addColorStop(1, 'rgba(' + GOLD + ',0)');
        ctx.fillStyle = gr;
        ctx.beginPath(); ctx.arc(sc.x, sc.y, rr, 0, TAU); ctx.fill();
      }
    }

    /* labels: leader lines on the canvas, text in the DOM */
    layoutLabels(anchors);
    ctx.globalAlpha = 1;
  }

  /* seven blades — each a small polygon that slides as the iris opens */
  function drawIrisBlades(dMin, dMax) {
    void dMin; void dMax;
    const open = S.irisOpen;
    const ap = lerp(5, 16, open);                    // aperture "radius"
    const R = 17.6, n = 7;
    const pt = iris;
    if (pt.alpha <= 0.003) return;
    for (let i = 0; i < n; i++) {
      const th = (i / n) * TAU + open * 0.55;
      const a1 = th + (TAU / n) * 1.55;
      const b0 = th + 0.12 + (1 - open) * 0.35, b1 = th + (TAU / n) * 0.92 + (1 - open) * 0.35;
      const loc = [
        [R * Math.cos(th), R * Math.sin(th), 1.2],
        [R * Math.cos(a1), R * Math.sin(a1), 1.2],
        [ap * Math.cos(b1), ap * Math.sin(b1), 1.2],
        [ap * Math.cos(b0), ap * Math.sin(b0), 1.2]
      ];
      const vv = loc.map((l) => toView(placePart(pt, l)));
      const pts = clipPoly(vv);
      if (pts.length < 3) continue;
      let d = 0; for (let k = 0; k < pts.length; k++) d += pts[k][2]; d /= pts.length;
      const sp = pts.map(proj);
      const lam = 0.35 + 0.25 * Math.sin(th * 2);
      items.push({ d: d - 0.01, kind: 0, pts: sp, fill: fillFor('blade', lam, 0, pt.alpha), m: 'blade', a: pt.alpha });
      for (let k = 0; k < sp.length; k++) {
        items.push({ d: d - 0.02, kind: 1, pts: [sp[k], sp[(k + 1) % sp.length]], m: k === 2 ? 'blade' : 'bladeDim', a: pt.alpha });
      }
    }
  }

  /* the rays: nine lines entering parallel, bent toward the axis by each
     glass surface, through the iris, converging to a soft disc on the sensor */
  function drawRays() {
    const e = S.explode;
    const stops = [
      [158, 1.0], [103, 0.86], [94, 0.78], [65, 0.62], [56, 0.52], [43, 0.44], [34, 0.36], [27, 0.3], [-26, 0.16]
    ];
    const N = 9, head = S.rays;
    for (let i = 0; i < N; i++) {
      const ang = (i / N) * TAU + 0.4;
      const r0 = i % 3 === 0 ? 20 : i % 3 === 1 ? 13 : 6.5;
      const pts3 = [];
      for (let s = 0; s < stops.length; s++) {
        const z = stops[s][0], f = stops[s][1];
        const r = r0 * f;
        /* exploded lens: the glass is further forward; keep the ray honest */
        const zz = z > 20 ? z + 40 * e * (z / 158) : z;
        pts3.push([AX + r * Math.cos(ang), r * Math.sin(ang), zz]);
      }
      /* the visible length grows from the front */
      const total = pts3.length - 1;
      const reach = head * total;
      const fi = Math.floor(reach), ft = reach - fi;
      const seq = pts3.slice(0, fi + 1);
      if (fi < total) {
        const a = pts3[fi], b = pts3[fi + 1];
        seq.push([lerp(a[0], b[0], ft), lerp(a[1], b[1], ft), lerp(a[2], b[2], ft)]);
      }
      const vv = seq.map(toView);
      /* clip each segment */
      const out = [];
      for (let k = 0; k < vv.length - 1; k++) {
        const c = clipSeg(vv[k], vv[k + 1]);
        if (!c) continue;
        if (!out.length) out.push(c[0]);
        out.push(c[1]);
      }
      if (out.length < 2) continue;
      let d = 0; for (let k = 0; k < out.length; k++) d += out[k][2]; d /= out.length;
      const fade = 0.35 + 0.65 * S.rays;
      items.push({ d: d - 0.5, kind: 2, pts: out.map(proj), a: fade * (1 - S.photoT) });
    }
  }

  /* the sensor's screen rectangle (centre + size), used for the glow and the
     photograph's zoom origin */
  function sensorScreen() {
    const pt = parts.find((q) => q.id === 'sensor');
    const c = toView(placePart(pt, [0, 0, 0]));
    if (c[2] <= NEAR) return null;
    const r = toView(placePart(pt, [11.15, 7.45, 0]));
    const cs = proj(c), rs = proj(r);
    const w = Math.abs(rs[0] - cs[0]) * 2, h = Math.abs(rs[1] - cs[1]) * 2;
    return { x: cs[0], y: cs[1], w, h };
  }

  /* ─── labels ───────────────────────────────────────────────────────────── */

  function buildLabels() {
    if (!labelsEl) return;
    labelsEl.textContent = '';
    labelDom = [];
    parts.forEach((pt) => {
      if (!pt.label) return;
      const el = document.createElement('span');
      el.className = 'instrument-label ' + (pt.side < 0 ? 'is-l' : 'is-r');
      el.textContent = pt.label;
      labelsEl.appendChild(el);
      labelDom.push({ pt, el, x: 0, y: 0, on: false });
      pt.labelEl = el;
    });
    measureLabels();
    if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
      document.fonts.ready.then(measureLabels);
    }
  }
  /* widths are read once (and again when the font arrives), never per frame */
  function measureLabels() {
    labelDom.forEach((ld) => { ld.pt.labelW = ld.el.offsetWidth || 80; });
  }

  function layoutLabels(anchors) {
    const L = S.label;
    const small = mqNarrow.matches;
    const reach = small ? 46 : 74;
    const lift = small ? 14 : 20;
    const placed = [];                 // rects already laid this frame
    const SLOTS = [0, 16, -16, 32, -32, 48, -48, 64, -64, 80, -80];
    /* stagger: labels arrive in part order, a beat apart */
    anchors.forEach((an, i) => {
      const pt = an.pt;
      if (!pt.labelEl) return;
      if (small && !pt.mobile) return;
      const stag = clamp01((L - 0.06 * (i % 8)) / 0.55);
      const ai = easeOut(stag);
      if (ai <= 0.001) { pt.labelEl.style.opacity = '0'; return; }
      const sx = an.s[0], sy = an.s[1];
      let side = pt.side;
      const lw = pt.labelW || 80;
      /* flip to the other side rather than run off the stage */
      if (side < 0 && sx - reach - lw < 6) side = 1;
      else if (side > 0 && sx + reach + lw > W - 6) side = -1;
      let lx = sx + side * reach, ly = sy - lift;
      ly = Math.max(12, Math.min(H - 12, ly));
      /* keep clear of every label already laid whose x-range this one
         crosses: take the nearest free 16px slot above or below (bounded) */
      const left = side < 0 ? lx - lw : lx, right = left + lw;
      for (let si = 0; si < SLOTS.length; si++) {
        const cy = Math.max(12, Math.min(H - 12, ly + SLOTS[si]));
        let clear = true;
        for (let k = 0; k < placed.length; k++) {
          const rc = placed[k];
          if (right > rc.l - 8 && left < rc.r + 8 && Math.abs(cy - rc.y) < 15) { clear = false; break; }
        }
        if (clear) { ly = cy; break; }
      }
      placed.push({ l: left, r: right, y: ly });
      /* leader */
      const kx = sx + side * (reach * 0.28);
      const al = (0.55 * ai) * (S.canvasA);
      ctx.strokeStyle = 'rgba(' + GOLD + ',' + al.toFixed(3) + ')';
      ctx.lineWidth = 0.9;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(kx, ly);
      ctx.lineTo(lx, ly);
      ctx.stroke();
      ctx.fillStyle = 'rgba(' + HEAT + ',' + (0.9 * ai).toFixed(3) + ')';
      ctx.beginPath(); ctx.arc(sx, sy, 1.7, 0, TAU); ctx.fill();
      ctx.strokeStyle = 'rgba(' + GOLD + ',' + (0.5 * ai).toFixed(3) + ')';
      ctx.beginPath(); ctx.arc(sx, sy, 4.5, 0, TAU); ctx.stroke();
      /* the text */
      const el = pt.labelEl;
      el.style.opacity = ai.toFixed(3);
      el.style.transform = 'translate(' + lx.toFixed(1) + 'px,' + ly.toFixed(1) + 'px) translate(' + (side < 0 ? '-100%' : '0') + ',-50%)';
      pt.labelShown = true;
    });
    /* hide labels with no anchor this frame */
    labelDom.forEach((ld) => {
      if (!anchors.some((an) => an.pt === ld.pt)) ld.el.style.opacity = '0';
    });
  }

  /* ─── the photograph ───────────────────────────────────────────────────── */

  function layoutPhoto() {
    if (!photo) return;
    /* a 3:2 box that covers the stage — the sensor's own proportion */
    let fw, fh;
    if (W / H > 1.5) { fw = W; fh = W / 1.5; } else { fh = H; fw = H * 1.5; }
    photoBox = { fw, fh };
    photo.style.width = fw.toFixed(1) + 'px';
    photo.style.height = fh.toFixed(1) + 'px';
    photo.style.left = ((W - fw) / 2).toFixed(1) + 'px';
    photo.style.top = ((H - fh) / 2).toFixed(1) + 'px';
  }

  function paintPhoto() {
    if (!photo) return;
    const A = S.photoA;
    if (A <= 0.002) {
      photo.style.opacity = '0';
      photo.style.visibility = 'hidden';
      return;
    }
    photo.style.visibility = 'visible';
    photo.style.opacity = A.toFixed(3);
    beginView();
    const sc = sensorScreen() || { x: W / 2, y: H / 2, w: W * 0.3, h: W * 0.2 };
    const t = S.photoT;
    const s0 = Math.max(0.02, sc.w / photoBox.fw);
    const s = lerp(s0, 1, t);
    const dx = lerp(sc.x - W / 2, 0, t), dy = lerp(sc.y - H / 2, 0, t);
    photo.style.transform = 'translate(' + dx.toFixed(1) + 'px,' + dy.toFixed(1) + 'px) scale(' + s.toFixed(4) + ')';
    if (photoImg) photoImg.style.filter = 'brightness(' + lerp(0.7, 1, t).toFixed(3) + ')';
  }

  /* ─── sizing, loop, scroll ─────────────────────────────────────────────── */

  function measure() {
    /* the canvas's own box — under reduced motion the stage also holds the
       photograph in flow, so the stage rect would squash the drawing */
    const r = canvas.getBoundingClientRect();
    const w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
    const d = Math.min(window.devicePixelRatio || 1, mqCoarse.matches ? 1.5 : 2);
    if (w !== W || h !== H || d !== dpr) {
      W = w; H = h; dpr = d;
      canvas.width = Math.round(w * d);
      canvas.height = Math.round(h * d);
      ctx.setTransform(d, 0, 0, d, 0, 0);
      focal = 1.12 * Math.min(W, H);
      if (W < H) focal = 1.25 * W;         // portrait: the lens must still fit
      layoutPhoto();
    }
    const rr = root.getBoundingClientRect();
    runwayTop = rr.top + (window.pageYOffset || 0);
    runwayLen = Math.max(1, rr.height - stage.getBoundingClientRect().height);
  }

  function readScroll() {
    const y = window.pageYOffset || 0;
    p = clamp01((y - runwayTop) / runwayLen);
  }

  function updateParts(dt) {
    const tt = now;
    const restored = seg(p, 0, 0.03);   // restored part-way down: already assembled
    for (let i = 0; i < parts.length; i++) {
      const pt = parts[i];
      const local = Math.max(clamp01((tt - 0.25 - pt.delay * 1.0) / 1.5), restored);
      pt.arrive = mqReduce.matches ? 1 : easeOutExpo(local);
      pt.alpha = mqReduce.matches ? 1 : clamp01(local * 2.2);
      pt.rot[0] = 0; pt.off[0] = 0; pt.off[1] = 0; pt.off[2] = 0;
    }
    /* the mirror lifts about its hinge: −45° takes it flat to the ceiling */
    const mir = parts.find((q) => q.id === 'mirror');
    mir.rot[0] = -Math.PI / 4 * S.mirrorUp;
    /* the curtains travel down */
    curtain1.off[1] = -19.6 * S.c1;
    curtain2.off[1] = -19.4 * S.c2;
    /* the sub-mirror rides the mirror (same part) — nothing else moves */
    }
  function decayDrag(dt) {
    if (dragging) return;
    const k = Math.exp(-dt / 1.4);
    dragYaw *= k; dragPitch *= k;
    if (Math.abs(dragYaw) < 0.01) dragYaw = 0;
    if (Math.abs(dragPitch) < 0.01) dragPitch = 0;
  }

  let rafOn = false, last = 0, lastKey = '';
  function tick(ts) {
    if (mqReduce.matches) { rafOn = false; return; }
    requestAnimationFrame(tick);
    if (!visible) { last = ts; return; }
    const dt = last ? Math.min(0.05, (ts - last) / 1000) : 0;
    last = ts;
    if (!t0) t0 = ts;
    now = (ts - t0) / 1000;
    decayDrag(dt);
    /* a frame is a pure function of these; while none of them moves the
       painted frame stands and the loop costs nothing. Time matters only
       through the entrances (< 4s) and the resting sway (p < 0.06). */
    const timed = now < 4 || p < 0.06;
    const key = p.toFixed(5) + '|' + dragYaw.toFixed(2) + '|' + dragPitch.toFixed(2) + '|' +
      (dragging ? 1 : 0) + '|' + (timed ? now.toFixed(3) : '-') + '|' + W + 'x' + H + '@' + dpr;
    if (key === lastKey) return;
    lastKey = key;
    frame(dt);
  }
  function frame(dt) {
    choreograph();
    updateParts(dt);
    render();
    paintPhoto();
    paintChrome();
  }
  function startRaf() {
    if (rafOn) return;
    rafOn = true; last = 0;
    requestAnimationFrame(tick);
  }

  const headEl = root.querySelector('.instrument-head');
  const hintEl = root.querySelector('.instrument-hint');
  const epochEl = root.querySelector('.instrument-epoch');
  const logWrap = logEl ? logEl.parentElement : null;
  let cueOn = null, axisOn = null;
  function paintChrome() {
    /* entrances: the chrome resolves after the instrument has assembled —
       or at once when the page is restored part-way down the runway */
    const restored = seg(p, 0, 0.03);
    const inA = mqReduce.matches ? 1 : Math.max(seg(now, 1.5, 2.9), restored);
    const inCue = mqReduce.matches ? 1 : Math.max(seg(now, 2.5, 3.7), restored);
    if (cue) {
      const vis = S.cueA * inCue;
      cue.style.opacity = vis.toFixed(3);
      const on = vis > 0.2;
      if (on !== cueOn) {           // attribute writes only on change
        cueOn = on;
        cue.style.pointerEvents = on ? 'auto' : 'none';
        cue.tabIndex = on ? 0 : -1;
        if (!on && document.activeElement === cue) cue.blur();
      }
    }
    const axis = S.swing >= 1;
    if (axis !== axisOn) { axisOn = axis; stage.classList.toggle('is-axis', axis); }
    if (headEl) headEl.style.opacity = (S.headA * inA).toFixed(3);
    if (hintEl) hintEl.style.opacity = (S.cueA * 0.9 * inCue).toFixed(3);
    if (epochEl) epochEl.style.opacity = S.epochA.toFixed(3);
    if (logWrap) logWrap.style.opacity = (0.9 * inA * (1 - seg(p, 0.95, 0.97))).toFixed(3);
  }

  /* reduced motion: one still — the exploded, labelled view, the photograph
     shown plainly beneath it (CSS un-pins the stage) */
  function still() {
    measure();
    now = 9;
    p = 0.44;
    dragYaw = 0; dragPitch = 0;
    frame(0);
    S.photoA = 1; S.photoT = 1;
    if (photo) { photo.style.visibility = 'visible'; photo.style.opacity = '1'; photo.style.transform = 'none'; }
    if (cue) { cue.style.opacity = '0'; cue.style.pointerEvents = 'none'; cue.tabIndex = -1; cueOn = false; }
    if (hintEl) hintEl.style.opacity = '0';
    if (epochEl) epochEl.style.opacity = '1';
    if (logEl) logEl.textContent = 'Exploded view · sixteen parts';
  }

  /* ─── interaction ──────────────────────────────────────────────────────── */

  /* drag to turn the instrument (vertical touch still scrolls: touch-action
     pan-y on the stage) */
  stage.addEventListener('pointerdown', (e) => {
    if (mqReduce.matches) return;
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    if (e.target === cue || (cue && cue.contains(e.target))) return;
    if (S.swing >= 1) return;           // on the axis the view is the light's, not the hand's
    dragging = true; dragX = e.clientX; dragY = e.clientY; dragVY = 0;
    stopAuto();
    try { stage.setPointerCapture(e.pointerId); } catch (err) { /* fine */ }
    stage.classList.add('is-dragging');
  });
  stage.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const dx = e.clientX - dragX, dy = e.clientY - dragY;
    dragX = e.clientX; dragY = e.clientY;
    const k = 1 - S.swing;              // the hand's weight fades through the swing
    dragYaw += dx * 0.38 * k;
    dragPitch = Math.max(-38, Math.min(38, dragPitch + dy * 0.22 * k));
  });
  const endDrag = () => { dragging = false; stage.classList.remove('is-dragging'); };
  stage.addEventListener('pointerup', endDrag);
  stage.addEventListener('pointercancel', endDrag);
  stage.addEventListener('lostpointercapture', endDrag);

  /* "Look inside": play the runway */
  let autoRaf = 0;
  function stopAuto() {
    if (autoRaf) { cancelAnimationFrame(autoRaf); autoRaf = 0; }
    document.documentElement.style.scrollBehavior = '';
    root.classList.remove('is-playing');
  }
  function playAuto() {
    if (mqReduce.matches) {
      window.scrollTo(0, runwayTop + runwayLen);
      return;
    }
    stopAuto();
    measure();
    const y0 = window.pageYOffset || 0;
    const y1 = runwayTop + runwayLen;
    const dur = Math.max(6000, 14000 * (1 - (y0 - runwayTop) / runwayLen));
    const start = performance.now();
    document.documentElement.style.scrollBehavior = 'auto';
    root.classList.add('is-playing');
    /* the button lets go of focus so Space/Enter read as page keys (stop) */
    if (document.activeElement === cue) cue.blur();
    const step = (ts) => {
      const u = clamp01((ts - start) / dur);
      const k = smooth(u);
      window.scrollTo(0, y0 + (y1 - y0) * k);
      if (u < 1) autoRaf = requestAnimationFrame(step);
      else stopAuto();
    };
    autoRaf = requestAnimationFrame(step);
  }
  if (cue) cue.addEventListener('click', () => { if (autoRaf) stopAuto(); else playAuto(); });
  ['wheel', 'touchstart', 'keydown'].forEach((ev) => {
    window.addEventListener(ev, (e) => {
      if (!autoRaf) return;
      if (ev === 'keydown') {
        /* the cue's own keys become its click (a toggle) — leave them to it */
        if (cue && (e.target === cue || cue.contains(e.target))) return;
        if (!/^(ArrowUp|ArrowDown|PageUp|PageDown|Home|End| |Spacebar|Escape|Tab)$/.test(e.key)) return;
      }
      stopAuto();
    }, { passive: true });
  });
  /* focus moving anywhere else ends the play — the browser's scroll-into-
     view must never fight the tween */
  document.addEventListener('focusin', (e) => {
    if (autoRaf && e.target !== cue) stopAuto();
  });

  /* scroll drives the runway */
  let scrollQueued = false;
  window.addEventListener('scroll', () => {
    readScroll();
    if (mqReduce.matches) return;
    /* when the loop is idle off-screen, still catch up the DOM once */
    if (!visible && !scrollQueued) {
      scrollQueued = true;
      requestAnimationFrame(() => { scrollQueued = false; });
    }
  }, { passive: true });

  /* visibility: pause when the stage is off-screen. Hidden tabs need no
     gate of their own — the browser stops requestAnimationFrame there — and
     some embedded viewers report "hidden" while plainly showing the page. */
  function syncVis() { visible = onScreen; }
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((es) => {
      onScreen = es.length ? es[es.length - 1].isIntersecting : true;
      syncVis();
    }, { threshold: 0 }).observe(stage);
  }
  document.addEventListener('visibilitychange', () => { tabShown = !document.hidden; last = 0; });

  /* sizing */
  if ('ResizeObserver' in window) {
    new ResizeObserver(() => { measure(); readScroll(); if (mqReduce.matches) still(); }).observe(stage);
  }
  window.addEventListener('resize', () => { measure(); readScroll(); if (mqReduce.matches) still(); });
  window.addEventListener('load', () => { measure(); readScroll(); });

  if (mqReduce.addEventListener) {
    mqReduce.addEventListener('change', () => {
      if (mqReduce.matches) { stopAuto(); still(); } else { t0 = 0; startRaf(); }
    });
  }

  /* go */
  buildLabels();
  measure();
  readScroll();
  parts.forEach((pt) => { pt.arrive = 0; pt.alpha = 0; });
  if (mqReduce.matches) {
    still();
  } else {
    startRaf();
  }
})();
