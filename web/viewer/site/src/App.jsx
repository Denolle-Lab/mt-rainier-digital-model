import { useCallback, useEffect, useRef, useState } from "react";
import { BUILD_COMMAND, BundleMissingError, loadBundle } from "./data/bundle.js";
import { StationLayer } from "./overlay/StationLayer.js";
import { QuakeLayers } from "./scene/quakes/quakeLayers.js";
import { RainierScene } from "./scene/RainierScene.js";
import { hasWebGL } from "./scene/webgl.js";
import NoWebGL from "./ui/NoWebGL.jsx";
import Controls from "./ui/Controls.jsx";
import GoTo from "./ui/GoTo.jsx";
import Header from "./ui/Header.jsx";
import LayerPanel from "./ui/LayerPanel.jsx";
import QuakeLegend from "./ui/QuakeLegend.jsx";
import Legend from "./ui/Legend.jsx";
import StationPanel from "./ui/StationPanel.jsx";
import Tooltip from "./ui/Tooltip.jsx";

export default function App() {
  const [bundle, setBundle] = useState(null), [error, setError] = useState(null);
  useEffect(() => { loadBundle().then(setBundle, setError); }, []);
  if (error) return <div className="app-message" role="alert"><div>{error.message}{error instanceof BundleMissingError && <code>{BUILD_COMMAND}</code>}</div></div>;
  if (!bundle) return <div className="app-message">Loading the atlas…</div>;
  if (!hasWebGL()) return <NoWebGL bundle={bundle} />;
  return <Atlas bundle={bundle} onError={setError} />;
}

export function detailText(frame, summit) {
  if (frame.summitFailures >= 3) return "summit detail limited";
  return frame.finest >= 0 ? `${Math.round(summit.levels[frame.finest].cell_z_km * 1000)} m` : "loading…";
}

function Atlas({ bundle, onError }) {
  const canvasRef = useRef(null), overlayRef = useRef(null), layerRef = useRef(null);
  const [scene, setScene] = useState(null), [siteId, setSiteId] = useState(null), [hover, setHover] = useState(null);
  const [detail, setDetail] = useState("loading…"), [active, setActive] = useState("home");

  const openSite = useCallback((site, sc) => {
    setSiteId(site.id); setActive(site.id); setHover(null);
    layerRef.current?.setSelected(site.id);
    if (site.onMap) sc.flyToSite(site);
  }, []);

  useEffect(() => {
    let sc, layer, cancelled = false, n = 0;
    RainierScene.create(canvasRef.current, bundle).then(s => {
      if (cancelled) { s.dispose(); return; }
      sc = s;
      layer = layerRef.current = new StationLayer(overlayRef.current, bundle, s, {
        onHover: (site, ev) => setHover(ev ? { site, x: ev.clientX, y: ev.clientY } : null),
        onClick: site => openSite(site, s),
      });
      if (bundle.quakes) s.layers = new QuakeLayers(s, bundle.quakes, overlayRef.current);
      s.onFrame = () => {
        layer.update();
        s.layers?.update((x, y, z) => s.project(x, y, z), s.camera.position.toArray(), (x, z) => s.elevKm(x, z) ?? -1e9);
        if (n++ % 15 === 0) setDetail(detailText(s.frame, bundle.summit));
      };
      setScene(s);
    }, onError);
    return () => { cancelled = true; layer?.dispose(); sc?.layers?.dispose(); sc?.dispose(); };
  }, [bundle, onError, openSite]);

  useEffect(() => {   // the panel pushes the right-hand controls inward, as in the Cascadia atlas
    document.documentElement.style.setProperty("--right-inset", siteId ? "472px" : "16px");
  }, [siteId]);

  const site = siteId ? bundle.siteById[siteId] : null;
  return (
    <>
      <canvas ref={canvasRef} className="atlas-scene" aria-label="3D map of Mount Rainier and its seismic network" />
      <div id="atlas-overlay" ref={overlayRef} />
      {scene && (
        <>
          <Header bundle={bundle} detail={detail} onPick={s => openSite(s, scene)} />
          <Controls scene={scene}>
            {scene.layers && <LayerPanel layers={scene.layers} scene={scene} onStations={on => layerRef.current?.setVisible(on)} />}
          </Controls>
          <GoTo majors={bundle.majors} active={active} onPlace={k => { setActive(k); scene.flyTo(k); }} onSite={s => openSite(s, scene)} />
          <Legend bundle={bundle}>{bundle.quakes && <QuakeLegend meta={bundle.quakes.meta} drawn={scene.layers?.drawn} />}</Legend>
          <Tooltip hover={hover} />
          {site && <StationPanel site={site} bundle={bundle} onFly={s => scene.flyToSite(s)}
            onClose={() => { setSiteId(null); layerRef.current?.setSelected(null); }} />}
        </>
      )}
    </>
  );
}
