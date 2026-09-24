import * as THREE from "three";

// Glow cloud: every event is a soft additive sprite, so dense zones build into light. Each fragment is placed on the
// sprite's plane in world space and dropped if it would sit above the ground, so no glow ever shows through terrain.
export function makeCloud(geometry, { pxScale, ground, camera }) {
  const m = new THREE.ShaderMaterial({
    uniforms: { uScale: pxScale, uGain: { value: 0.07 }, uViewInv: { value: camera.matrixWorld }, ...ground.uniforms },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float mag; attribute float ground; uniform float uScale;
      varying vec3 vCv; varying float vSize;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vSize = 0.16 + 0.052 * clamp(mag, 0.0, 4.5);             // sprite diameter, km
        vCv = mv.xyz;
        gl_PointSize = vSize * uScale / -mv.z;
        gl_Position = position.y > ground ? vec4(2.0, 2.0, 2.0, 1.0) : projectionMatrix * mv;   // above ground: clipped away
      }`,
    fragmentShader: ground.glsl + `
      uniform float uGain; uniform mat4 uViewInv;
      varying vec3 vCv; varying float vSize;
      void main() {
        vec2 d = gl_PointCoord - 0.5;
        vec3 wp = (uViewInv * vec4(vCv + vec3(d.x, -d.y, 0.0) * vSize, 1.0)).xyz;
        if (wp.y > groundKm(wp.xz) - 0.02) discard;
        float a = exp(-dot(d, d) * 12.0) * uGain;
        gl_FragColor = vec4(vec3(0.22, 0.45, 0.92) * a, 1.0);
      }`,
  });
  const p = new THREE.Points(geometry, m);
  p.frustumCulled = false; p.renderOrder = 4;
  return p;
}
