export const ease = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function moveStep(held, cam, target, dt) {
  let fx = target[0] - cam[0], fz = target[2] - cam[2];
  const fl = Math.hypot(fx, fz) || 1; fx /= fl; fz /= fl;
  const rx = -fz, rz = fx;   // right = forward × up
  let x = 0, z = 0;
  if (held.has("ArrowUp")) { x += fx; z += fz; }
  if (held.has("ArrowDown")) { x -= fx; z -= fz; }
  if (held.has("ArrowRight")) { x += rx; z += rz; }
  if (held.has("ArrowLeft")) { x -= rx; z -= rz; }
  const len = Math.hypot(x, z);
  if (!len) return [0, 0, 0];
  const dist = Math.hypot(cam[0] - target[0], cam[1] - target[1], cam[2] - target[2]);
  const k = (0.3 * dist * dt) / len;
  return [x * k, 0, z * k];
}

export const isTypingTarget = el =>
  !!el && (el.isContentEditable || el.contentEditable === "true" || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));

// prefers-reduced-motion: flights jump to their end and uniform transitions snap.
export const motionDuration = (ms, reduced) => (reduced ? 0 : ms);
export const approach = (value, target, dt, speed, reduced) =>
  reduced ? target : value + (target - value) * Math.min(1, dt * speed);

// macOS sends no keyup for other keys while Cmd is held, so modified arrows never start a move.
export const isMoveKey = e =>
  !!e.key?.startsWith("Arrow") && !(e.metaKey || e.ctrlKey || e.altKey) && !isTypingTarget(e.target);

// On-screen navigation: rotate about the vertical through the target (dAz, degrees, positive = counter-clockwise
// seen from above), tilt (dPol, degrees, positive = toward the horizon) and zoom (factor on the distance). The
// polar angle stays within [minPol, maxPol] radians; northUp sets the azimuth so the view looks north (-z).
export function orbitPose(cam, target, { dAz = 0, dPol = 0, zoom = 1, northUp = false } = {}, minPol = 0.02, maxPol = Math.PI - 0.02) {
  const [dx, dy, dz] = [cam[0] - target[0], cam[1] - target[1], cam[2] - target[2]];
  let r = Math.hypot(dx, dy, dz) || 1;
  let theta = Math.atan2(dx, dz), phi = Math.acos(Math.max(-1, Math.min(1, dy / r)));
  theta = northUp ? 0 : theta + (dAz * Math.PI) / 180;
  phi = Math.max(minPol, Math.min(maxPol, phi + (dPol * Math.PI) / 180));
  r *= zoom;
  const s = Math.sin(phi);
  return [target[0] + r * s * Math.sin(theta), target[1] + r * Math.cos(phi), target[2] + r * s * Math.cos(theta)];
}
