import { useEffect, useRef, useState } from "react";
import { BUILD_COMMAND, BundleMissingError, loadBundle } from "./data/bundle.js";
import { StationLayer } from "./overlay/StationLayer.js";
import { RainierScene } from "./scene/RainierScene.js";

export default function App() {
  const [bundle, setBundle] = useState(null), [error, setError] = useState(null);
  useEffect(() => { loadBundle().then(setBundle, setError); }, []);
  if (error) return <div className="app-message" role="alert"><div>{error.message}{error instanceof BundleMissingError && <code>{BUILD_COMMAND}</code>}</div></div>;
  if (!bundle) return <div className="app-message">Loading the atlas…</div>;
  return <Atlas bundle={bundle} onError={setError} />;
}

function Atlas({ bundle, onError }) {
  const canvasRef = useRef(null), overlayRef = useRef(null), layerRef = useRef(null);
  const [scene, setScene] = useState(null);
  useEffect(() => {
    let sc, layer, cancelled = false;
    RainierScene.create(canvasRef.current, bundle).then(s => {
      if (cancelled) { s.dispose(); return; }
      sc = s;
      layer = layerRef.current = new StationLayer(overlayRef.current, bundle, s, { onClick: site => s.flyToSite(site) });
      s.onFrame = () => layer.update();
      setScene(s);
    }, onError);
    return () => { cancelled = true; layer?.dispose(); sc?.dispose(); };
  }, [bundle, onError]);
  return (
    <>
      <canvas ref={canvasRef} className="atlas-scene" aria-label="3D map of Mount Rainier and its seismic network" />
      <div id="atlas-overlay" ref={overlayRef} />
    </>
  );
}
