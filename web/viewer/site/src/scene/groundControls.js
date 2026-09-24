// Above ground, a see-through ground is drawn after the underground layers so they read as beneath it;
// below ground it is drawn first so the layers stay in front.
export const terrainOrder = under => (under ? -1 : 10);

// The cut removes the terrain where dot(xz, n) > offset; n points at the removed side (90° = south).
export function cutUniform(angleDeg, offsetKm) {
  const a = (angleDeg * Math.PI) / 180;
  return [Math.cos(a), 0, Math.sin(a), offsetKm];
}

export const isUnder = (cam, elevKm, flat = 0) => cam[1] < (elevKm(cam[0], cam[2]) ?? 0) * (1 - flat);
