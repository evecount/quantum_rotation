# Cybrdeck Glass Kit (portable)

A framework-agnostic port of CybrDeck-Website's "clear optical glass" design language —
refraction, not frosted blur — for plain static HTML/JS projects with no build step,
no React, no Tailwind. Built for `quantum_rotation`, but the whole folder is meant to be
copied into other projects as-is.

Source of truth this was ported from: `CybrDeck-Website/src/components/ui/ContourGlassButton.tsx`,
`LiquidGlassMarquee.tsx`, `GlassLensDefs.tsx`, and the `.cd-lens-glass` tokens in
`src/app/globals.css`, plus the `.agents/skills/cybrdeck-liquid-glass` and
`cybrdeck-glass-buttons` skill docs in that repo (read those first if you need to go
deeper than this port covers).

## Files

| File | What it is |
| --- | --- |
| `cybrdeck-glass.css` | The `.cd-lens-glass` refraction classes (size tiers sm/default/lg/xl) + the static glass-button chassis (`.cd-glass-btn`). |
| `glass-lens-defs.js` | Mounts the SVG `feDisplacementMap` filters the CSS above references. Call once per page. |
| `glass-button.js` | `RimGlassButton` — the Canvas2D orbiting-specular hover effect for buttons. |
| `liquid-glass-shader.js` | The verbatim per-channel-dispersion GLSL shader, plus a `createLiquidGlassMaterial(THREE, opts)` helper for three.js. |
| `demo.html` | Standalone page exercising all three — open directly in a browser to verify. |

## Quick start

```html
<link rel="stylesheet" href="assets/cybrdeck-glass/cybrdeck-glass.css">
<script src="assets/cybrdeck-glass/glass-lens-defs.js"></script>
<script src="assets/cybrdeck-glass/glass-button.js"></script>

<button class="cd-glass-btn cd-glass-btn--primary">
  <span class="cd-glass-btn__label">Launch Simulation</span>
</button>

<div class="cd-lens-glass" style="padding: 20px; border-radius: 16px;">
  A refractive glass panel over whatever's behind it.
</div>

<script>
  mountCybrdeckLensDefs();
  CybrdeckGlassButtons.mountAll('.cd-glass-btn');
</script>
```

## The three optical primitives, and when to reach for which

| Surface must bend… | Use | Why |
| --- | --- | --- |
| Arbitrary page content behind an HTML box (buttons, cards, panels) | `.cd-lens-glass` (CSS + `glass-lens-defs.js`) | `backdrop-filter` is the only thing that samples the live DOM behind an element. |
| A self-contained drawn object with an orbiting specular ribbon (a CTA button) | `glass-button.js` (`RimGlassButton`) | Full manual control of body/edge/rim; no page content to bend. |
| Its own content only, wants real per-channel dispersion (a banner, a marquee, a HUD strip) | `liquid-glass-shader.js` (WebGL/GLSL) | A canvas owns the texture it refracts; CSS can offset all channels equally but cannot split R/G/B — that split is most of what reads as glass instead of blur. |

## The optical invariants (glass, not a frosted rectangle)

1. **Refract, don't blur.** Bend the background inward, hard at the rim, untouched through the middle.
2. **Dispersion is per-channel.** This is what `liquid-glass-shader.js` gives you that CSS can't.
3. **Curvature only in the outer lip** — center content should sit in the flat middle of a lens surface, not warp at its own edges.
4. **Dark body, near-zero tint.** `--cd-obsidian: 9,15,27` is the recurring ink tone. No white face-wash gradient — all the light lives on the edges.

## Gotchas preserved from the source (read before tuning)

- **Canvas sizing:** size from `el.offsetWidth/offsetHeight` (border-box), not `getBoundingClientRect()` (lies under 3D transforms) and not CSS `inset:0`/`100%` (resolves against the *padding* box on an absolutely-positioned child — squashes the effect by roughly a border-width).
- **`SHEAR` vs `GRATING` incommensurability** in `glass-button.js`'s band baking is intentional — if the shear equaled a whole striation period, every filament would peak together and the band would bead into pearls instead of a clean diagonal grating.
- **DPR caps by role, not by device:** focal/interactive canvases (a button someone's pointer is on) cap at 2; ambient/background canvases should cap lower (1.5–1.75) — see `threeui-canvas-craft` in the source skill docs.
- **`backdrop-filter` fallback ordering:** the `blur()` declaration must come *before* the `url(#cd-lens-*)` one in the same CSS rule — engines that reject SVG filters in `backdrop-filter` fall back to the last declaration they understand, so order is the feature-detection mechanism, not `@supports`.
- **`prefers-reduced-motion` freezes the orbit, never blanks the surface** — `glass-button.js` stops advancing `phase` but still renders a settled frame.

## Honesty note on this port

This was reconstructed from a detailed procedural description of the original ~1050-line
`ContourGlassButton.tsx` (exact constants, algorithm structure, named gotchas), not copied
byte-for-byte — the original is a React/Canvas2D component this port intentionally
re-implements without React. Visually close, not guaranteed pixel-identical to the
CybrDeck site. If exact parity ever matters, diff against the live source component.
