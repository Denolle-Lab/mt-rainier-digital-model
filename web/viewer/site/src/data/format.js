export const fmtElev = m => `${Math.round(m).toLocaleString("en-US")} m`;
export const fmtSince = date => `since ${String(date).slice(0, 4)}`;
export const fmtMonths = ([a, b]) => `${a?.slice(0, 7) ?? "?"} – ${b?.slice(0, 7) ?? "?"}`;   // an ended instrument
export const fmtRate = hz => `${hz >= 1 ? Math.round(hz) : hz} Hz`;
