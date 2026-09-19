/**
 * Cybrdeck Glass Kit — Liquid glass refraction shader.
 * Ported (GLSL verbatim) from CybrDeck-Website's LiquidGlassMarquee.tsx.
 *
 * The trick `backdrop-filter` structurally cannot do: PER-CHANNEL dispersion.
 * R/G/B are sampled at three different displacement magnitudes (1.00/0.93/0.86),
 * not one bent UV reused for all channels — that channel split is what reads
 * as real glass instead of a blurred pane.
 *
 * Exposes both the raw GLSL source (for a raw WebGL2 canvas) and a
 * `createLiquidGlassMaterial(THREE, opts)` helper for three.js.
 */
(function (global) {
  'use strict';

  // WebGL2 / GLSL ES 300 source, exactly as documented from the source component.
  const VERTEX_SHADER_GLSL3 = `#version 300 es
in vec2 aPos;
out vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

  const FRAGMENT_SHADER_GLSL3 = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 outColor;

uniform sampler2D uContent;
uniform vec2  uRes;
uniform float uContentW;
uniform float uScroll;
uniform vec2  uPointer;
uniform float uPress;
uniform float uDpr;

float baseH(vec2 p) {
  float ny = p.y / uRes.y;
  return smoothstep(0.0, 0.18, ny) * smoothstep(1.0, 0.82, ny);
}

float pressH(vec2 p) {
  if (uPress <= 0.001) return 0.0;
  vec2 d = (p - uPointer) / (vec2(165.0, 82.0) * uDpr);
  return -uPress * exp(-dot(d, d) * 1.6);
}

vec4 sampleContent(vec2 px, float lod) {
  vec2 uv = vec2((px.x + uScroll) / uContentW, px.y / uRes.y);
  return textureLod(uContent, uv, lod);
}

void main() {
  vec2 px = vec2(vUv.x, 1.0 - vUv.y) * uRes;

  float e = 1.5 * uDpr;
  vec2 nBase = vec2(
    baseH(px + vec2(e, 0.0)) - baseH(px - vec2(e, 0.0)),
    baseH(px + vec2(0.0, e)) - baseH(px - vec2(0.0, e))) / (2.0 * e);
  vec2 nPress = vec2(
    pressH(px + vec2(e, 0.0)) - pressH(px - vec2(e, 0.0)),
    pressH(px + vec2(0.0, e)) - pressH(px - vec2(0.0, e))) / (2.0 * e);
  vec2 n = nBase + nPress;

  vec2 bend = -(nBase * 130.0 + nPress * 1100.0) * uDpr;
  vec4 r = sampleContent(px + bend * 1.00, 0.0);
  vec4 g = sampleContent(px + bend * 0.93, 0.0);
  vec4 b = sampleContent(px + bend * 0.86, 0.0);
  vec3 col = vec3(r.r, g.g, b.b);
  float a = max(max(r.a, g.a), b.a);

  vec3 glow = sampleContent(px + bend * 2.2, 4.0).rgb
            + sampleContent(px + bend * 4.0, 6.0).rgb * 0.7;

  float lipPx = 1.5 * uDpr;
  float lip = (1.0 - smoothstep(0.0, lipPx, px.y)) * 0.42
            + (1.0 - smoothstep(0.0, lipPx, uRes.y - px.y)) * 0.17;

  vec3 body = vec3(0.007, 0.010, 0.017);

  vec3 outRgb = col + glow * 0.08 + body + lip;
  float alpha = clamp(a + 0.018 + lip + length(n) * 0.06, 0.0, 1.0);

  outColor = vec4(outRgb, alpha);
}`;

  // GLSL ES 100 (WebGL1 / three.js ShaderMaterial default) equivalent.
  // `textureLod` -> `texture2D` (no explicit LOD in WebGL1 core; the glow
  // terms fall back to base-LOD sampling, a minor fidelity trade-off).
  const VERTEX_SHADER_GLSL1 = `
attribute vec2 aPos;
varying vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

  const FRAGMENT_SHADER_GLSL1 = `
precision highp float;
varying vec2 vUv;

uniform sampler2D uContent;
uniform vec2  uRes;
uniform float uContentW;
uniform float uScroll;
uniform vec2  uPointer;
uniform float uPress;
uniform float uDpr;

float baseH(vec2 p) {
  float ny = p.y / uRes.y;
  return smoothstep(0.0, 0.18, ny) * smoothstep(1.0, 0.82, ny);
}

float pressH(vec2 p) {
  if (uPress <= 0.001) return 0.0;
  vec2 d = (p - uPointer) / (vec2(165.0, 82.0) * uDpr);
  return -uPress * exp(-dot(d, d) * 1.6);
}

vec4 sampleContent(vec2 px) {
  vec2 uv = vec2((px.x + uScroll) / uContentW, px.y / uRes.y);
  return texture2D(uContent, uv);
}

void main() {
  vec2 px = vec2(vUv.x, 1.0 - vUv.y) * uRes;

  float e = 1.5 * uDpr;
  vec2 nBase = vec2(
    baseH(px + vec2(e, 0.0)) - baseH(px - vec2(e, 0.0)),
    baseH(px + vec2(0.0, e)) - baseH(px - vec2(0.0, e))) / (2.0 * e);
  vec2 nPress = vec2(
    pressH(px + vec2(e, 0.0)) - pressH(px - vec2(e, 0.0)),
    pressH(px + vec2(0.0, e)) - pressH(px - vec2(0.0, e))) / (2.0 * e);
  vec2 n = nBase + nPress;

  vec2 bend = -(nBase * 130.0 + nPress * 1100.0) * uDpr;
  vec4 r = sampleContent(px + bend * 1.00);
  vec4 g = sampleContent(px + bend * 0.93);
  vec4 b = sampleContent(px + bend * 0.86);
  vec3 col = vec3(r.r, g.g, b.b);
  float a = max(max(r.a, g.a), b.a);

  float lipPx = 1.5 * uDpr;
  float lip = (1.0 - smoothstep(0.0, lipPx, px.y)) * 0.42
            + (1.0 - smoothstep(0.0, lipPx, uRes.y - px.y)) * 0.17;

  vec3 body = vec3(0.007, 0.010, 0.017);

  vec3 outRgb = col + body + lip;
  float alpha = clamp(a + 0.018 + lip + length(n) * 0.06, 0.0, 1.0);

  gl_FragColor = vec4(outRgb, alpha);
}`;

  /**
   * Creates a THREE.ShaderMaterial implementing the liquid-glass refraction.
   * `opts.map` should be a THREE.CanvasTexture (or similar) with
   * wrapS=RepeatWrapping, wrapT=ClampToEdgeWrapping, minFilter=LinearFilter.
   */
  function createLiquidGlassMaterial(THREE, opts) {
    opts = opts || {};
    const uniforms = {
      uContent: { value: opts.map || null },
      uRes: { value: new THREE.Vector2(opts.width || 1, opts.height || 1) },
      uContentW: { value: opts.contentWidth || 1 },
      uScroll: { value: 0 },
      uPointer: { value: new THREE.Vector2(0, 0) },
      uPress: { value: 0 },
      uDpr: { value: Math.min(window.devicePixelRatio || 1, 2) },
    };
    // three.js ShaderMaterial auto-injects `position`/`uv` attributes and the
    // model/view/projection matrices, so the vertex stage is just a pass-through.
    const threeVertexShader = `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `;
    return new THREE.ShaderMaterial({
      uniforms,
      vertexShader: threeVertexShader,
      fragmentShader: FRAGMENT_SHADER_GLSL1,
      transparent: true,
      depthWrite: false,
    });
  }

  global.CybrdeckLiquidGlass = {
    VERTEX_SHADER_GLSL3, FRAGMENT_SHADER_GLSL3,
    VERTEX_SHADER_GLSL1, FRAGMENT_SHADER_GLSL1,
    createLiquidGlassMaterial,
  };
})(typeof window !== 'undefined' ? window : this);
