import * as THREE from "three";

// Terrain shader for the overview and every summit tile. Styles (eased): 0 photo, 1 mono hillshade, 2 contours.
// uFlat flattens to 2D. uClip cuts away one side of a vertical plane; uAlpha makes the ground see-through;
// uHole lets the summit tiles replace the overview; skirts and the underside draw as dark rock.
const VERT = `
  attribute float skirt; uniform float uFlat;
  varying vec2 vUv; varying vec3 vPos; varying vec3 vN; varying float vSkirt; varying float vElev;
  void main() {
    vUv = uv; vN = normal; vSkirt = skirt; vElev = position.y * 1000.0;
    vec3 p = position; p.y *= 1.0 - uFlat;
    vec4 wp = modelMatrix * vec4(p, 1.0); vPos = wp.xyz;
    gl_Position = projectionMatrix * viewMatrix * wp;
  }`;
const FRAG = `
  uniform sampler2D uMap; uniform vec4 uClip, uHole;
  uniform float uClipOn, uAlpha, uHoleOn, uUnder, uStyle, uFlat;
  varying vec2 vUv; varying vec3 vPos; varying vec3 vN; varying float vSkirt; varying float vElev;
  float contour(float interval, float width) {
    float v = vElev / interval; float f = abs(fract(v - 0.5) - 0.5); float w = fwidth(v) * width;
    return 1.0 - smoothstep(0.0, w, f);
  }
  void main() {
    if (uClipOn > 0.5 && dot(vPos.xz, uClip.xz) > uClip.w) discard;
    if (vSkirt > 0.0001 && uUnder > 0.5) discard;   // skirts only hide cracks seen from above
    if (uHoleOn > 0.5 && vPos.x > uHole.x && vPos.x < uHole.y && vPos.z > uHole.z && vPos.z < uHole.w) discard;
    vec3 n = normalize(vN);
    float shade = clamp(dot(n, normalize(vec3(-0.6, 1.0, -0.7))), 0.0, 1.0);
    vec3 photo = texture2D(uMap, vUv).rgb * mix(0.78, 1.12, shade);   // the photo carries its own shadows
    float g = mix(0.30, 0.66, smoothstep(300.0, 4300.0, vElev));
    vec3 mono = vec3(g) * mix(0.32, 1.18, shade);
    float minor = contour(100.0, 1.0), major = contour(500.0, 1.5);
    vec3 fill = vec3(0.085) * mix(1.0, mix(0.55, 1.6, shade), 1.0 - uFlat);
    vec3 lines = mix(fill, vec3(0.55), minor * 0.5);
    lines = mix(lines, vec3(0.88), major * 0.9);
    vec3 col = uStyle < 1.0 ? mix(photo, mono, uStyle) : mix(mono, lines, uStyle - 1.0);
    if (!gl_FrontFacing || vSkirt > 0.0001) col = vec3(0.10, 0.10, 0.095) + col * 0.12;
    gl_FragColor = vec4(col, uAlpha);
  }`;

export function terrainMaterial(U, map, { hole = false } = {}) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uMap: { value: map }, uClip: U.clip, uClipOn: U.clipOn, uAlpha: U.alpha, uUnder: U.under, uStyle: U.style, uFlat: U.flat,
      uHole: U.hole, uHoleOn: hole ? U.holeOn : { value: 0 },
    },
    vertexShader: VERT, fragmentShader: FRAG, side: THREE.DoubleSide,
  });
}
