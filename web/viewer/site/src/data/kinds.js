// Instrument kinds in fixed order. Colors are the dataviz reference dark slots without blue, which belongs to the
// earthquake layers; validated with validate_palette.js against #121211. Every kind also has its own glyph.
// Exception: GNSS is a steel blue (#157db3, OKLCH L 0.56 C 0.12 H 239) instead of the green slot, which read as the
// geophone green. It keeps the palette's tone (validate_palette.js, dark, #121211: passes; protan ΔE 7.8 to the
// accelerometer is in the 6-8 band, covered by the glyphs) and is told from the earthquake dark blue by its
// diamond glyph and by sitting on the ground, not below it.
export const KINDS = [
  { key: "seismometer", label: "Seismometer", color: "#d95926", glyph: "triangle" },
  { key: "geophone", label: "Geophone", color: "#199e70", glyph: "circle" },
  { key: "infrasound", label: "Infrasound", color: "#c98500", glyph: "hexagon" },
  { key: "accelerometer", label: "Accelerometer", color: "#d55181", glyph: "square" },
  { key: "gnss", label: "GNSS", color: "#157db3", glyph: "diamond" },   // steel blue, not the geophone green
  { key: "tiltmeter", label: "Tiltmeter", color: "#9085e9", glyph: "bar" },
  { key: "strainmeter", label: "Borehole strainmeter", color: "#e66767", glyph: "cross" },
  // beyond the eight categorical slots: folded kinds in neutral grey, told apart by glyph and the hover card
  { key: "hydromet", label: "Weather, snow, streamflow", color: "#b9b7ad", glyph: "drop" },
  { key: "other", label: "Other (magnetotelluric)", color: "#8b8980", glyph: "ring" },
];
export const KIND_BY_KEY = Object.fromEntries(KINDS.map(k => [k.key, k]));
