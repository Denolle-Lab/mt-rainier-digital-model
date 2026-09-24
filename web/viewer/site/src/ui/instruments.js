import { KIND_BY_KEY } from "../data/kinds.js";
import { fmtRate } from "../data/format.js";

export const instrumentLabel = i =>
  i.kind === "seismometer" ? `${i.band === "broadband" ? "Broadband" : "Short-period"} seismometer` : KIND_BY_KEY[i.kind].label;
export const instrumentLine = i => `${instrumentLabel(i)} · ${i.channels.join(" ")} · ${fmtRate(i.rate)}`;
export const operators = site => [...new Set(site.stations.map(s => s.operator))];
