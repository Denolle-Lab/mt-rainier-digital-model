// Phones and tablets get a lighter scene: the browser kills a tab that holds the full terrain (2.2 M vertices),
// the summit tiles and a 4080-px drape at once, which shows as a white page. `?lite=1` / `?lite=0` force it.
export function liteProfile(win = typeof window === "undefined" ? undefined : window) {
  const force = win?.location ? new URLSearchParams(win.location.search).get("lite") : null;
  if (force === "1" || force === "0") return force === "1";
  const coarse = typeof win?.matchMedia === "function" && win.matchMedia("(pointer: coarse)").matches;
  const lowMem = typeof win?.navigator?.deviceMemory === "number" && win.navigator.deviceMemory <= 4;
  return coarse || lowMem;
}

// full: desktop; lite: every second terrain and summit sample (4x fewer vertices), a half-width drape,
// fewer summit tiles kept and refined later, down to 2 m (level 2) not 1 m, no MSAA, pixel ratio capped at 1.5
export const PROFILES = {
  full: { terrainStride: 1, summitStride: 1, summitCap: 360, summitInflight: 6, summitRefine: 2.5, summitMaxLevel: Infinity, photoMaxWidth: Infinity, antialias: true, maxPixelRatio: 2 },
  lite: { terrainStride: 2, summitStride: 2, summitCap: 64, summitInflight: 3, summitRefine: 1.25, summitMaxLevel: 2, photoMaxWidth: 2048, antialias: false, maxPixelRatio: 1.5 },
};

export const deviceProfile = (win) => PROFILES[liteProfile(win) ? "lite" : "full"];
