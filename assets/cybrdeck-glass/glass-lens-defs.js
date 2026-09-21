/**
 * Cybrdeck Glass Kit — SVG lens filter mounter.
 * Ported from CybrDeck-Website's GlassLensDefs.tsx. Vanilla JS, no React.
 *
 * Mounts a hidden <svg> once containing one <filter> per size tier
 * (sm/default/lg/xl) plus a cursor-follow lens, all driven by an
 * feDisplacementMap sampling a baked lens-map data URI. Call
 * `mountCybrdeckLensDefs()` once per page (idempotent) before using
 * `.cd-lens-glass` anywhere.
 */
(function (global) {
  'use strict';

  const SCALES = { sm: 8, default: 11, lg: 13, xl: 15 };
  const BUMP_PX = 120;

  // Lens map: R = horizontal bend, G = vertical bend, 128 = neutral.
  // Flat at 128 through the middle, ramps to 0/255 only in an edge band —
  // this is what keeps the centre of a surface undistorted while the rim bends.
  const LENS_MAP_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="90" viewBox="0 0 300 90" preserveAspectRatio="none">
<defs>
<linearGradient id="x" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="rgb(0,0,0)"/>
<stop offset="0.06" stop-color="rgb(64,0,0)"/>
<stop offset="0.17" stop-color="rgb(128,0,0)"/>
<stop offset="0.83" stop-color="rgb(128,0,0)"/>
<stop offset="0.94" stop-color="rgb(192,0,0)"/>
<stop offset="1" stop-color="rgb(255,0,0)"/>
</linearGradient>
<linearGradient id="y" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="rgb(0,0,0)"/>
<stop offset="0.10" stop-color="rgb(0,64,0)"/>
<stop offset="0.30" stop-color="rgb(0,128,0)"/>
<stop offset="0.70" stop-color="rgb(0,128,0)"/>
<stop offset="0.90" stop-color="rgb(0,192,0)"/>
<stop offset="1" stop-color="rgb(0,255,0)"/>
</linearGradient>
</defs>
<rect width="300" height="90" fill="url(#x)"/>
<rect width="300" height="90" fill="url(#y)" style="mix-blend-mode:screen"/>
</svg>`;

  // Bump map: the pointer-follow bulge — neutral centre, peak at ~1/4 out,
  // neutral rim again, so hover deformation has no hard edge.
  const BUMP_MAP_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
<defs>
<radialGradient id="bx" cx="50%" cy="50%" r="50%">
<stop offset="0%" stop-color="rgb(128,0,0)"/>
<stop offset="25%" stop-color="rgb(255,0,0)"/>
<stop offset="60%" stop-color="rgb(128,0,0)"/>
<stop offset="100%" stop-color="rgb(128,0,0)"/>
</radialGradient>
<radialGradient id="by" cx="50%" cy="50%" r="50%">
<stop offset="0%" stop-color="rgb(0,128,0)"/>
<stop offset="25%" stop-color="rgb(0,255,0)"/>
<stop offset="60%" stop-color="rgb(0,128,0)"/>
<stop offset="100%" stop-color="rgb(0,128,0)"/>
</radialGradient>
</defs>
<rect width="120" height="120" fill="url(#bx)"/>
<rect width="120" height="120" fill="url(#by)" style="mix-blend-mode:screen"/>
</svg>`;

  function dataUri(svg) {
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  }

  function mountCybrdeckLensDefs() {
    if (document.getElementById('cd-lens-defs-root')) return; // idempotent

    const lensMap = dataUri(LENS_MAP_SVG);
    const bumpMap = dataUri(BUMP_MAP_SVG);

    const svgNS = 'http://www.w3.org/2000/svg';
    const xlinkNS = 'http://www.w3.org/1999/xlink';
    const root = document.createElementNS(svgNS, 'svg');
    root.setAttribute('id', 'cd-lens-defs-root');
    root.setAttribute('aria-hidden', 'true');
    root.setAttribute('focusable', 'false');
    root.style.cssText = 'position:fixed;width:0;height:0;pointer-events:none;';

    const defs = document.createElementNS(svgNS, 'defs');

    function setHref(el, href) {
      el.setAttributeNS(xlinkNS, 'xlink:href', href);
      el.setAttribute('href', href);
    }

    // One filter per size tier.
    Object.keys(SCALES).forEach((tier) => {
      const id = tier === 'default' ? 'cd-lens-default' : `cd-lens-${tier}`;
      const filter = document.createElementNS(svgNS, 'filter');
      filter.setAttribute('id', id);
      filter.setAttribute('x', '0');
      filter.setAttribute('y', '0');
      filter.setAttribute('width', '100%');
      filter.setAttribute('height', '100%');
      filter.setAttribute('color-interpolation-filters', 'sRGB');

      const feImage = document.createElementNS(svgNS, 'feImage');
      setHref(feImage, lensMap);
      feImage.setAttribute('x', '0');
      feImage.setAttribute('y', '0');
      feImage.setAttribute('width', '100%');
      feImage.setAttribute('height', '100%');
      feImage.setAttribute('preserveAspectRatio', 'none');
      feImage.setAttribute('result', 'map');

      const disp = document.createElementNS(svgNS, 'feDisplacementMap');
      disp.setAttribute('in', 'SourceGraphic');
      disp.setAttribute('in2', 'map');
      disp.setAttribute('scale', String(SCALES[tier]));
      disp.setAttribute('xChannelSelector', 'R');
      disp.setAttribute('yChannelSelector', 'G');

      const blur = document.createElementNS(svgNS, 'feGaussianBlur');
      blur.setAttribute('stdDeviation', '0.35');

      filter.appendChild(feImage);
      filter.appendChild(disp);
      filter.appendChild(blur);
      defs.appendChild(filter);
    });

    // Cursor-follow lens: strength driven at runtime via #cd-lens-cursor-gain
    // (feFuncA slope/intercept) and position via #cd-lens-cursor-bump (x/y).
    const cursorFilter = document.createElementNS(svgNS, 'filter');
    cursorFilter.setAttribute('id', 'cd-lens-cursor');
    cursorFilter.setAttribute('x', '0');
    cursorFilter.setAttribute('y', '0');
    cursorFilter.setAttribute('width', '100%');
    cursorFilter.setAttribute('height', '100%');
    cursorFilter.setAttribute('color-interpolation-filters', 'sRGB');

    const baseImg = document.createElementNS(svgNS, 'feImage');
    setHref(baseImg, lensMap);
    baseImg.setAttribute('x', '0');
    baseImg.setAttribute('y', '0');
    baseImg.setAttribute('width', '100%');
    baseImg.setAttribute('height', '100%');
    baseImg.setAttribute('preserveAspectRatio', 'none');
    baseImg.setAttribute('result', 'base');

    const bumpImg = document.createElementNS(svgNS, 'feImage');
    bumpImg.setAttribute('id', 'cd-lens-cursor-bump');
    setHref(bumpImg, bumpMap);
    bumpImg.setAttribute('x', String(-BUMP_PX * 4));
    bumpImg.setAttribute('y', String(-BUMP_PX * 4));
    bumpImg.setAttribute('width', String(BUMP_PX));
    bumpImg.setAttribute('height', String(BUMP_PX));
    bumpImg.setAttribute('preserveAspectRatio', 'none');
    bumpImg.setAttribute('result', 'bumpRaw');

    const compTransfer = document.createElementNS(svgNS, 'feComponentTransfer');
    compTransfer.setAttribute('in', 'bumpRaw');
    compTransfer.setAttribute('result', 'bump');
    const funcA = document.createElementNS(svgNS, 'feFuncA');
    funcA.setAttribute('id', 'cd-lens-cursor-gain');
    funcA.setAttribute('type', 'linear');
    funcA.setAttribute('slope', '0');
    funcA.setAttribute('intercept', '0');
    compTransfer.appendChild(funcA);

    const composite = document.createElementNS(svgNS, 'feComposite');
    composite.setAttribute('in', 'bump');
    composite.setAttribute('in2', 'base');
    composite.setAttribute('operator', 'over');
    composite.setAttribute('result', 'map');

    const cursorDisp = document.createElementNS(svgNS, 'feDisplacementMap');
    cursorDisp.setAttribute('id', 'cd-lens-cursor-disp');
    cursorDisp.setAttribute('in', 'SourceGraphic');
    cursorDisp.setAttribute('in2', 'map');
    cursorDisp.setAttribute('scale', '15');
    cursorDisp.setAttribute('xChannelSelector', 'R');
    cursorDisp.setAttribute('yChannelSelector', 'G');

    const cursorBlur = document.createElementNS(svgNS, 'feGaussianBlur');
    cursorBlur.setAttribute('stdDeviation', '0.35');

    cursorFilter.appendChild(baseImg);
    cursorFilter.appendChild(bumpImg);
    cursorFilter.appendChild(compTransfer);
    cursorFilter.appendChild(composite);
    cursorFilter.appendChild(cursorDisp);
    cursorFilter.appendChild(cursorBlur);
    defs.appendChild(cursorFilter);

    root.appendChild(defs);
    document.body.appendChild(root);
  }

  /**
   * Drives the cursor-follow lens (#cd-lens-cursor) toward a page-space
   * (clientX, clientY) point with a given 0..1 strength. Call this from a
   * pointermove handler on whatever element should carry the cursor bulge.
   */
  function setCybrdeckCursorLens(clientX, clientY, strength) {
    const bump = document.getElementById('cd-lens-cursor-bump');
    const gain = document.getElementById('cd-lens-cursor-gain');
    if (!bump || !gain) return;
    bump.setAttribute('x', String(clientX - BUMP_PX / 2));
    bump.setAttribute('y', String(clientY - BUMP_PX / 2));
    const s = Math.max(0, Math.min(1, strength));
    gain.setAttribute('slope', String(s));
  }

  global.mountCybrdeckLensDefs = mountCybrdeckLensDefs;
  global.setCybrdeckCursorLens = setCybrdeckCursorLens;
})(typeof window !== 'undefined' ? window : this);
