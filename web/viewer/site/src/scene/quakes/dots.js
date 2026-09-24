import * as THREE from "three";

// One crisp point per event with a fixed screen size by magnitude. Events above the ground are not drawn.
export function makeDots(geometry, { dpr }) {
  const m = new THREE.ShaderMaterial({
    uniforms: { uDpr: { value: dpr } }, transparent: true, depthWrite: false,
    vertexShader: `
      attribute float mag; attribute float ground; uniform float uDpr;
      void main() {
        gl_PointSize = position.y > ground - 0.01 ? 0.0 : (1.6 + 1.1 * clamp(mag + 0.5, 0.0, 5.0)) * uDpr;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      void main() {
        float r = length(gl_PointCoord - 0.5);
        if (r > 0.5) discard;
        gl_FragColor = vec4(0.62, 0.77, 0.96, 0.55 * (1.0 - smoothstep(0.35, 0.5, r)));
      }`,
  });
  const p = new THREE.Points(geometry, m);
  p.frustumCulled = false; p.renderOrder = 5;
  return p;
}
