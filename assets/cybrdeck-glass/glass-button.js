/**
 * Cybrdeck Glass Kit — Rim Glass Button (Canvas2D, vanilla JS port).
 *
 * Ported from CybrDeck-Website's ContourGlassButton.tsx `rim` effect: a
 * spectral dispersion band sits faintly around the whole perimeter; a
 * blown-out white specular head orbits the rim (~1 pass per PERIOD),
 * leaning toward the cursor, dragging a bloom and a warm-inside/cool-outside
 * chromatic fringe. The label stays on dark glass the whole time.
 *
 * Usage:
 *   <button class="cd-glass-btn cd-glass-btn--primary">
 *     <span class="cd-glass-btn__label">Launch</span>
 *   </button>
 *   <script>
 *     document.querySelectorAll('.cd-glass-btn').forEach(el => new RimGlassButton(el));
 *   </script>
 *
 * No React, no build step. Call `.destroy()` to tear down listeners/rAF.
 */
(function (global) {
  'use strict';

  const RIM = {
    PERIOD: 4.6,   // s per autonomous orbit
    PAD: 30,       // css px canvas is inflated past the pill so bloom escapes
    NF: 7,         // filament count across the band
    BAND: 4.4,     // band width, css px
    SPAN: 0.62,    // fraction of spectrum spanned across the band
    HUEDRIFT: 1.3, // spectrum sweeps this many times around the perimeter
    GRATING: 2.4,  // striation pitch, css px
    GRAT_A: 0.2,   // striation contrast
    SHEAR: 1.7,    // filament lean — kept incommensurate with GRATING on purpose
    FIL_A: 0.42,
    FLOOR: 0.18,   // band brightness on the unlit arc
    ENV_R: 2.4,    // lit-arc envelope radius, in button-heights
    CORE_A: 1.0,
    CA_A: 0.55,    // chromatic-aberration fringe alpha
    PULL: 0.28,    // how far the highlight leans toward the pointer
    BLOOM_OUT: 38, BLOOM_OUT_A: 0.13,
    BLOOM_IN: 17, BLOOM_IN_A: 0.44,
    BLOOM_STRETCH: 2.2,
  };

  const RIM_SPECTRUM = [
    [255, 46, 66], [255, 132, 28], [255, 226, 92], [104, 255, 132],
    [56, 226, 255], [72, 120, 255], [176, 74, 255],
  ];

  function rimSpectral(t) {
    const n = RIM_SPECTRUM.length;
    const x = ((t % 1) + 1) % 1;
    const seg = x * n;
    const i0 = Math.floor(seg) % n;
    const i1 = (i0 + 1) % n;
    const f = seg - Math.floor(seg);
    const a = RIM_SPECTRUM[i0], b = RIM_SPECTRUM[i1];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  }

  // Shortest signed distance from a to b on a 0..1 ring (handles wraparound).
  function rimWrap(d) {
    let x = d % 1;
    if (x > 0.5) x -= 1;
    if (x < -0.5) x += 1;
    return x;
  }

  /**
   * Builds a piecewise outline (line/arc segments) for a pill or rounded-rect,
   * parametrised by arc length. point(u) -> {x,y,nx,ny} for u in [0,1).
   */
  function buildOutline(W, H, shape, cornerR) {
    const segs = [];
    if (shape === 'pill') {
      const r = H / 2;
      const straight = Math.max(0, W - 2 * r);
      // top edge, left->right at y=0 (outward normal up)
      segs.push({ len: straight, at: (t) => ({ x: r + straight * t, y: 0, nx: 0, ny: -1 }) });
      // right cap: -90deg -> 90deg around (W-r, r)
      segs.push({ len: Math.PI * r, at: (t) => {
        const a = -Math.PI / 2 + Math.PI * t;
        return { x: W - r + r * Math.cos(a), y: r + r * Math.sin(a), nx: Math.cos(a), ny: Math.sin(a) };
      } });
      // bottom edge, right->left at y=H (outward normal down)
      segs.push({ len: straight, at: (t) => ({ x: (W - r) - straight * t, y: H, nx: 0, ny: 1 }) });
      // left cap: 90deg -> 270deg around (r, r)
      segs.push({ len: Math.PI * r, at: (t) => {
        const a = Math.PI / 2 + Math.PI * t;
        return { x: r + r * Math.cos(a), y: r + r * Math.sin(a), nx: Math.cos(a), ny: Math.sin(a) };
      } });
    } else {
      const r = Math.min(cornerR, W / 2, H / 2);
      const wStraight = Math.max(0, W - 2 * r);
      const hStraight = Math.max(0, H - 2 * r);
      // top edge
      segs.push({ len: wStraight, at: (t) => ({ x: r + wStraight * t, y: 0, nx: 0, ny: -1 }) });
      // top-right corner: -90 -> 0
      segs.push({ len: (Math.PI / 2) * r, at: (t) => {
        const a = -Math.PI / 2 + (Math.PI / 2) * t;
        return { x: W - r + r * Math.cos(a), y: r + r * Math.sin(a), nx: Math.cos(a), ny: Math.sin(a) };
      } });
      // right edge
      segs.push({ len: hStraight, at: (t) => ({ x: W, y: r + hStraight * t, nx: 1, ny: 0 }) });
      // bottom-right corner: 0 -> 90
      segs.push({ len: (Math.PI / 2) * r, at: (t) => {
        const a = 0 + (Math.PI / 2) * t;
        return { x: W - r + r * Math.cos(a), y: H - r + r * Math.sin(a), nx: Math.cos(a), ny: Math.sin(a) };
      } });
      // bottom edge
      segs.push({ len: wStraight, at: (t) => ({ x: (W - r) - wStraight * t, y: H, nx: 0, ny: 1 }) });
      // bottom-left corner: 90 -> 180
      segs.push({ len: (Math.PI / 2) * r, at: (t) => {
        const a = Math.PI / 2 + (Math.PI / 2) * t;
        return { x: r + r * Math.cos(a), y: H - r + r * Math.sin(a), nx: Math.cos(a), ny: Math.sin(a) };
      } });
      // left edge
      segs.push({ len: hStraight, at: (t) => ({ x: 0, y: (H - r) - hStraight * t, nx: -1, ny: 0 }) });
      // top-left corner: 180 -> 270
      segs.push({ len: (Math.PI / 2) * r, at: (t) => {
        const a = Math.PI + (Math.PI / 2) * t;
        return { x: r + r * Math.cos(a), y: r + r * Math.sin(a), nx: Math.cos(a), ny: Math.sin(a) };
      } });
    }
    const total = segs.reduce((s, seg) => s + Math.max(seg.len, 1e-6), 0);
    let acc = 0;
    for (const seg of segs) {
      seg.start = acc / total;
      seg.frac = Math.max(seg.len, 1e-6) / total;
      acc += Math.max(seg.len, 1e-6);
    }
    function point(u) {
      let x = ((u % 1) + 1) % 1;
      for (const seg of segs) {
        if (x < seg.start + seg.frac || seg === segs[segs.length - 1]) {
          const local = Math.min(1, Math.max(0, (x - seg.start) / seg.frac));
          return seg.at(local);
        }
      }
      return segs[0].at(0);
    }
    return { point, total };
  }

  class RimGlassButton {
    constructor(el, opts) {
      opts = opts || {};
      this.el = el;
      this.shape = opts.shape || (el.dataset.cdShape) || 'pill';
      this.cornerR = opts.cornerR || 16;

      this.canvas = el.querySelector('.cd-glass-btn__fx') || document.createElement('canvas');
      if (!this.canvas.classList.contains('cd-glass-btn__fx')) {
        this.canvas.className = 'cd-glass-btn__fx';
        el.insertBefore(this.canvas, el.firstChild);
      }
      this.ctx = this.canvas.getContext('2d');

      this.state = { isHovered: false, targetX: 50, targetY: 50, currentX: 50, currentY: 50, intensity: 0, targetIntensity: 0 };
      this.phase = 0;
      this.lastT = performance.now();
      this.raf = null;
      this.running = false;
      this.reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      this._onMove = this._onMove.bind(this);
      this._onEnter = this._onEnter.bind(this);
      this._onLeave = this._onLeave.bind(this);
      this._tick = this._tick.bind(this);
      this._resize = this._resize.bind(this);

      this.ro = new ResizeObserver(this._resize);
      this.ro.observe(this.el);
      this._resize();

      el.addEventListener('pointermove', this._onMove);
      el.addEventListener('pointerenter', this._onEnter);
      el.addEventListener('pointerleave', this._onLeave);

      // Draw one settled frame immediately (reduced-motion / initial paint).
      this._bake();
      this._draw();
    }

    destroy() {
      if (this.raf) cancelAnimationFrame(this.raf);
      this.ro.disconnect();
      this.el.removeEventListener('pointermove', this._onMove);
      this.el.removeEventListener('pointerenter', this._onEnter);
      this.el.removeEventListener('pointerleave', this._onLeave);
    }

    _resize() {
      // Border-box sizing from offsetWidth/offsetHeight, not getBoundingClientRect
      // (which lies under 3D transforms) and not inset:0 (padding-box mismatch).
      const dpr = Math.min(window.devicePixelRatio || 1, 2); // focal control: cap 2
      this.W = this.el.offsetWidth;
      this.H = this.el.offsetHeight;
      this.dpr = dpr;
      const pad = RIM.PAD;
      this.canvas.style.left = (-pad - this.el.clientLeft) + 'px';
      this.canvas.style.top = (-pad - this.el.clientTop) + 'px';
      this.canvas.style.width = (this.W + pad * 2) + 'px';
      this.canvas.style.height = (this.H + pad * 2) + 'px';
      this.canvas.width = Math.round((this.W + pad * 2) * dpr);
      this.canvas.height = Math.round((this.H + pad * 2) * dpr);
      this.outline = buildOutline(this.W * dpr, this.H * dpr, this.shape, this.cornerR * dpr);
      this._bake();
      this._draw();
    }

    _bake() {
      if (!this.outline) return;
      const dpr = this.dpr;
      const W = this.W * dpr, H = this.H * dpr;
      const band = document.createElement('canvas');
      band.width = W + RIM.PAD * 2 * dpr;
      band.height = H + RIM.PAD * 2 * dpr;
      const bctx = band.getContext('2d');
      bctx.translate(RIM.PAD * dpr, RIM.PAD * dpr);
      bctx.globalCompositeOperation = 'lighter';

      const N_SAMPLES = 240;
      for (let f = 0; f < RIM.NF; f++) {
        const off = (f - (RIM.NF - 1) / 2) * (RIM.BAND * dpr / RIM.NF);
        bctx.beginPath();
        for (let i = 0; i <= N_SAMPLES; i++) {
          const u = i / N_SAMPLES;
          const p = this.outline.point(u);
          const x = p.x + p.nx * off;
          const y = p.y + p.ny * off;
          if (i === 0) bctx.moveTo(x, y); else bctx.lineTo(x, y);
        }
        bctx.closePath();
        const [r, g, b] = rimSpectral(f * RIM.SPAN / RIM.NF);
        const grating = 0.5 + 0.5 * Math.sin((f * (this.outline.total || 1)) / (RIM.GRATING * dpr) * RIM.SHEAR);
        const a = RIM.FIL_A * (1 - RIM.GRAT_A + RIM.GRAT_A * grating);
        bctx.strokeStyle = `rgba(${r | 0},${g | 0},${b | 0},${a.toFixed(3)})`;
        bctx.lineWidth = Math.max(1, dpr);
        bctx.stroke();
      }
      this._band = band;
    }

    _onMove(e) {
      const rect = this.el.getBoundingClientRect();
      this.state.targetX = ((e.clientX - rect.left) / rect.width) * 100;
      this.state.targetY = ((e.clientY - rect.top) / rect.height) * 100;
    }
    _onEnter() {
      this.state.isHovered = true;
      this.state.targetIntensity = 1;
      this._startLoop();
    }
    _onLeave() {
      this.state.isHovered = false;
      this.state.targetIntensity = 0;
      this.state.targetX = 50;
      this.state.targetY = 50;
    }

    _startLoop() {
      if (this.running) return;
      this.running = true;
      this.lastT = performance.now();
      this.raf = requestAnimationFrame(this._tick);
    }

    _tick(t) {
      const dt = Math.min(0.05, (t - this.lastT) / 1000);
      this.lastT = t;
      const s = this.state;
      s.currentX += (s.targetX - s.currentX) * 0.12;
      s.currentY += (s.targetY - s.currentY) * 0.12;
      s.intensity += (s.targetIntensity - s.intensity) * 0.1;
      if (!this.reduced) this.phase += dt;

      this._draw();

      if (s.isHovered || s.intensity > 0.01) {
        this.raf = requestAnimationFrame(this._tick);
      } else {
        this.running = false;
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      }
    }

    _draw() {
      const ctx = this.ctx, dpr = this.dpr;
      if (!ctx || !this.outline) return;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      const I = this.state.intensity;
      if (I <= 0.001 && !this.reduced) return;

      ctx.save();
      ctx.translate(RIM.PAD * dpr, RIM.PAD * dpr);

      const orbitU = this.reduced ? 0.08 : (this.phase / RIM.PERIOD) % 1;

      // Find nearest rim point to the pointer (bounded sample search).
      const px = (this.state.currentX / 100) * this.W * dpr;
      const py = (this.state.currentY / 100) * this.H * dpr;
      let bestU = orbitU, bestD = Infinity;
      const SAMPLES = 48;
      for (let i = 0; i < SAMPLES; i++) {
        const u = i / SAMPLES;
        const p = this.outline.point(u);
        const d = (p.x - px) * (p.x - px) + (p.y - py) * (p.y - py);
        if (d < bestD) { bestD = d; bestU = u; }
      }
      const du = rimWrap(bestU - orbitU);
      const ease = 1 - Math.min(1, Math.abs(du) / 0.35);
      const headU = orbitU + du * RIM.PULL * Math.max(0, ease);
      const head = this.outline.point(headU);

      // Band: FLOOR everywhere, full toward the head via a radial envelope mask.
      if (this._band) {
        ctx.globalAlpha = RIM.FLOOR + (1 - RIM.FLOOR) * 0 + RIM.FLOOR * 0; // base
        ctx.globalAlpha = RIM.FLOOR;
        ctx.drawImage(this._band, 0, 0);

        const envR = RIM.ENV_R * this.H * dpr;
        const mask = document.createElement('canvas');
        mask.width = this._band.width; mask.height = this._band.height;
        const mctx = mask.getContext('2d');
        mctx.drawImage(this._band, 0, 0);
        mctx.globalCompositeOperation = 'destination-in';
        const g = mctx.createRadialGradient(head.x, head.y, 0, head.x, head.y, envR);
        g.addColorStop(0, 'rgba(255,255,255,1)');
        g.addColorStop(1, 'rgba(255,255,255,0)');
        mctx.fillStyle = g;
        mctx.fillRect(0, 0, mask.width, mask.height);
        ctx.globalAlpha = I;
        ctx.drawImage(mask, 0, 0);
      }

      // Bloom at the head, stretched along the rim tangent.
      ctx.globalAlpha = I;
      ctx.globalCompositeOperation = 'lighter';
      const tangAngle = Math.atan2(-head.nx, head.ny); // tangent = normal rotated 90deg
      ctx.save();
      ctx.translate(head.x, head.y);
      ctx.rotate(tangAngle);
      ctx.scale(RIM.BLOOM_STRETCH, 1);
      let bg = ctx.createRadialGradient(0, 0, 0, 0, 0, RIM.BLOOM_OUT * dpr);
      bg.addColorStop(0, `rgba(175,205,255,${RIM.BLOOM_OUT_A})`);
      bg.addColorStop(1, 'rgba(175,205,255,0)');
      ctx.fillStyle = bg;
      ctx.beginPath(); ctx.arc(0, 0, RIM.BLOOM_OUT * dpr, 0, Math.PI * 2); ctx.fill();
      let bg2 = ctx.createRadialGradient(0, 0, 0, 0, 0, RIM.BLOOM_IN * dpr);
      bg2.addColorStop(0, `rgba(255,238,205,${RIM.BLOOM_IN_A})`);
      bg2.addColorStop(1, 'rgba(255,238,205,0)');
      ctx.fillStyle = bg2;
      ctx.beginPath(); ctx.arc(0, 0, RIM.BLOOM_IN * dpr, 0, Math.PI * 2); ctx.fill();
      ctx.restore();

      // Core + chromatic fringe rings, stroked as gradients centred on the head.
      const ringW = 3.0 * dpr;
      const drawRing = (offset, color, alpha) => {
        ctx.beginPath();
        const SAMP = 160;
        for (let i = 0; i <= SAMP; i++) {
          const u = i / SAMP;
          const p = this.outline.point(u);
          const x = p.x + p.nx * offset, y = p.y + p.ny * offset;
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.closePath();
        const grad = ctx.createRadialGradient(head.x, head.y, 0, head.x, head.y, RIM.ENV_R * this.H * dpr * 0.7);
        grad.addColorStop(0, `rgba(${color},${alpha})`);
        grad.addColorStop(1, `rgba(${color},0)`);
        ctx.strokeStyle = grad;
        ctx.lineWidth = offset === 0 ? ringW : ringW * 0.55;
        ctx.stroke();
      };
      drawRing(0, '255,255,255', RIM.CORE_A * I);
      drawRing(-1.5 * dpr, '255,214,170', RIM.CA_A * I);
      drawRing(1.5 * dpr, '170,214,255', RIM.CA_A * I);

      ctx.restore();
    }
  }

  global.RimGlassButton = RimGlassButton;
  global.CybrdeckGlassButtons = {
    mountAll(selector) {
      const els = document.querySelectorAll(selector || '.cd-glass-btn');
      const instances = [];
      els.forEach((el) => instances.push(new RimGlassButton(el)));
      return instances;
    },
  };
})(typeof window !== 'undefined' ? window : this);
