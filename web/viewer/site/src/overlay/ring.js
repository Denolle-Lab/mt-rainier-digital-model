import { KIND_BY_KEY, KINDS } from "../data/kinds.js";

// Station marker: a ring with one segment per instrument kind, the same ring as the Cascadia atlas's site markers.
export const ringSize = n => (n > 3 ? 24 : n > 1 ? 20 : 16);

export function ringSvg(kinds, size) {
  const ks = KINDS.map(k => k.key).filter(k => kinds.includes(k));
  const n = ks.length, R = size / 2 - 2.5, cx = size / 2, gap = n > 1 ? Math.min(0.28, 1.4 / n) : 0;
  const pt = a => `${(cx + R * Math.cos(a)).toFixed(2)} ${(cx + R * Math.sin(a)).toFixed(2)}`;
  const segs = ks.map((k, i) => {
    const a0 = (i / n) * Math.PI * 2 - Math.PI / 2 + gap / 2, a1 = ((i + 1) / n) * Math.PI * 2 - Math.PI / 2 - gap / 2;
    const d = n === 1 ? `M ${cx - R} ${cx} a ${R} ${R} 0 1 0 ${2 * R} 0 a ${R} ${R} 0 1 0 ${-2 * R} 0`
                      : `M ${pt(a0)} A ${R} ${R} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${pt(a1)}`;
    return `<path class="seg" data-kind="${k}" d="${d}" fill="none" stroke="${KIND_BY_KEY[k].color}" stroke-width="3.2"/>`;
  }).join("");
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">` +
    `<circle cx="${cx}" cy="${cx}" r="${R + 2.2}" fill="rgba(12,12,11,0.72)"/>${segs}<circle cx="${cx}" cy="${cx}" r="1.8" fill="#ecebe6"/></svg>`;
}
