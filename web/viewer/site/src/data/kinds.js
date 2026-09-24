// Instrument kinds in fixed order. Colors are the dataviz reference dark slots without blue, which belongs to the
// earthquake layers; validated with validate_palette.js against #121211. Every kind also has its own glyph.
export const KINDS = [
  { key: "seismometer", label: "Seismometer", color: "#d95926", glyph: "triangle" },
  { key: "geophone", label: "Geophone", color: "#199e70", glyph: "circle" },
  { key: "infrasound", label: "Infrasound", color: "#c98500", glyph: "hexagon" },
  { key: "accelerometer", label: "Accelerometer", color: "#d55181", glyph: "square" },
  { key: "gnss", label: "GNSS", color: "#008300", glyph: "diamond" },
  { key: "tiltmeter", label: "Tiltmeter", color: "#9085e9", glyph: "bar" },
  { key: "strainmeter", label: "Borehole strainmeter", color: "#e66767", glyph: "cross" },
];
export const KIND_BY_KEY = Object.fromEntries(KINDS.map(k => [k.key, k]));
