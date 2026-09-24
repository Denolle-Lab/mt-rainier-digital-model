export function hasWebGL() {
  try {
    if (!window.WebGLRenderingContext) return false;
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}
