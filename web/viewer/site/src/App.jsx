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
import ModelLayers from "./ui/ModelLayers.jsx";
import ModelLegend from "./ui/ModelLegend.jsx";
import ModelReadout from "./ui/ModelReadout.jsx";
import MobileDock from "./ui/MobileDock.jsx";
import NavPad from "./ui/NavPad.jsx";
import SubsurfacePanel from "./ui/SubsurfacePanel.jsx";
import SensorTip from "./ui/SensorTip.jsx";
import { SensorPoints } from "./scene/SensorPoints.js";
import { MassEventPoints } from "./scene/MassEventPoints.js";
import { DEFAULT_MASS_FILTER, loadMassEvents, massCounts } from "./data/massEvents.js";
import MassFilter from "./ui/MassFilter.jsx";
import MassTip from "./ui/MassTip.jsx";
import { DEFAULT_FILTER, classifyMarker, extraSites, kindCounts, loadSensors, passes } from "./data/sensors.js";
import { ModelVolume, loadVolumeMeta } from "./scene/ModelVolume.js";
import HelpPanel, { HelpHint, markHelpSeen } from "./ui/HelpPanel.jsx";
import HudDock from "./ui/HudDock.jsx";
import QuakeLegend from "./ui/QuakeLegend.jsx";
import RelocatedPanel from "./ui/RelocatedPanel.jsx";
import { RelocatedQuakes } from "./scene/quakes/relocated.js";
import { DEFAULT_RELOCATED, loadRelocated } from "./data/relocated.js";
import Attribution from "./ui/Attribution.jsx";
import EventsPanel from "./ui/EventsPanel.jsx";
import { RainEvent } from "./scene/RainEvent.js";
import { loadEvent, loadEvents } from "./data/events.js";
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
  const [detail, setDetail] = useState("loading…"), [active, setActive] = useState("home"), [modelKey, setModelKey] = useState(null), [sheet, setSheet] = useState(null), [dock, setDock] = useState(() => new Set()), [helpOpened, setHelpOpened] = useState(false), [volume, setVolume] = useState(null), [sens, setSens] = useState(null), [sfilter, setSfilter] = useState(DEFAULT_FILTER);
  const [mass, setMass] = useState(null), [mfilter, setMfilter] = useState(DEFAULT_MASS_FILTER);
  const [reloc, setReloc] = useState(null), [event, setEvent] = useState(null);

  const openSite = useCallback((site, sc) => {
    setSiteId(site.id); setActive(site.id); setHover(null); setSheet(null);
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
      loadSensors(bundle.base).then(inv => {
        if (!inv || cancelled) return;
        const extras = extraSites(inv, bundle.stations);
        s.sensors = new SensorPoints(s, extras, inv.das); s.sensors.setFilter(DEFAULT_FILTER);
        setSens({ all: [...bundle.stations.sites.filter(x => x.onMap).map(classifyMarker), ...extras], das: inv.das, points: s.sensors, notes: inv.notes ?? {} });
      });
      if (bundle.model) loadMassEvents(bundle.base).then(doc => {
        if (!doc || cancelled) return;
        s.mass = new MassEventPoints(s, doc); s.mass.setFilter(DEFAULT_MASS_FILTER);
        setMass({ doc, points: s.mass });
      });
      loadRelocated(bundle.base).then(r => {   // optional: the relocated catalogue (rainier3d S26)
        if (!r || cancelled) return;
        s.reloc = new RelocatedQuakes(s, r); s.reloc.set(DEFAULT_RELOCATED);
        setReloc(s.reloc);
      });
      loadEvents(bundle.base).then(async list => {   // optional: hydrometeorological events (rainier3d S29)
        if (!list.length || cancelled) return;
        const ev = await loadEvent(bundle.base, list[list.length - 1]).catch(() => null);
        if (!ev || cancelled) return;
        s.event = new RainEvent(s, ev, { drops: s.profile?.terrainStride > 1 ? 9000 : 24000 });
        setEvent(s.event);
      });
      if (bundle.model) loadVolumeMeta(bundle.model.base).then(meta => {
        if (meta && !cancelled) { s.volume = new ModelVolume(s, meta, bundle.model.base); setVolume(s.volume); }
      });
      s.onFrame = () => {
        layer.update();
        s.volume?.update();
        s.event?.update(1 / 60);
        s.layers?.update((x, y, z) => s.project(x, y, z), s.camera.position.toArray(), (x, z) => s.elevKm(x, z) ?? -1e9);
        if (n++ % 15 === 0) setDetail(detailText(s.frame, bundle.summit));
      };
      setScene(s);
    }, onError);
    return () => { cancelled = true; layer?.dispose(); sc?.layers?.dispose(); sc?.volume?.dispose(); sc?.sensors?.dispose(); sc?.mass?.dispose(); sc?.reloc?.dispose(); sc?.event?.dispose(); sc?.dispose(); };
  }, [bundle, onError, openSite]);

  useEffect(() => {   // the panel pushes the right-hand controls inward, as in the Cascadia atlas
    document.documentElement.style.setProperty("--right-inset", siteId ? "472px" : "16px");
  }, [siteId]);

  const site = siteId ? bundle.siteById[siteId] : null;
  const toggleDock = key => setDock(o => { const n = new Set(o); if (!n.delete(key)) n.add(key); return n; });
  // ? (the nav pad or the first-visit hint) opens Help: in the dock on a desktop, as a bottom sheet on a phone
  const openHelp = () => { setDock(o => new Set(o).add("help")); setSheet("help"); markHelpSeen(); setHelpOpened(true); };
  const applyFilter = f => {
    setSfilter(f); sens?.points.setFilter(f);
    layerRef.current?.setFilter(x => passes(classifyMarker(x), f));
  };
  const sensorLegend = sens && { filter: sfilter, onFilter: applyFilter, counts: kindCounts(sens.all, sfilter), das: sens.das };
  const modelLayer = modelKey ? bundle.model.byKey[modelKey] : null;
  const flowLayer = bundle.model?.byKey.mass_flows;
  const showFlows = on => {   // the flow deposits are a draped model layer: the same slot as the layer menu
    setModelKey(on ? "mass_flows" : null);
    scene.setOverlay(on ? bundle.model.base + flowLayer.texture : null, { categorical: true });
  };
  const massLegend = mass && {
    doc: mass.doc, filter: mfilter, counts: massCounts(mass.points.events, mfilter),
    onFilter: f => { setMfilter(f); mass.points.setFilter(f); },
    flows: modelKey === "mass_flows", onFlows: flowLayer ? showFlows : null,
  };
  return (
    <>
      <canvas ref={canvasRef} className="atlas-scene" aria-label="3D map of Mount Rainier and its seismic network" />
      <div id="atlas-overlay" ref={overlayRef} />
      {scene && (
        <>
          <Header bundle={bundle} detail={detail} onPick={s => openSite(s, scene)} />
          <HudDock open={dock} onToggle={toggleDock} items={[
            // View: camera and ground. Then one panel per theme: earthquakes (every catalogue), mass movements,
            // ground sensors, and the structural models (surface layers and the model below ground).
            { key: "view", label: "View", icon: "view", node: (
              <Controls scene={scene}>
                <LayerPanel layers={scene.layers} scene={scene} parts={["ground"]} />
              </Controls>) },
            ...(bundle.quakes || reloc ? [{ key: "quakes", label: "Earthquakes", icon: "quakes", node: (
              <div className="panel quakes-panel">
                {scene.layers && <LayerPanel layers={scene.layers} scene={scene} parts={["quakes"]} />}
                {bundle.quakes && <QuakeLegend meta={bundle.quakes.meta} drawn={scene.layers?.drawn} />}
                {reloc && <RelocatedPanel points={reloc} />}
              </div>) }] : []),
            ...(massLegend ? [{ key: "mass", label: "Mass movements", icon: "mass", node: (
              <div className="panel mass-panel"><MassFilter {...massLegend} /></div>) }] : []),
            { key: "sensors", label: "Sensors", icon: "sensors", node: (
              <Legend bundle={bundle} sensors={sensorLegend}>
                <LayerPanel layers={scene.layers} scene={scene} parts={["stations"]} onStations={on => layerRef.current?.setVisible(on)} />
              </Legend>) },
            ...(bundle.model ? [{ key: "model", label: "Models", icon: "model", node: (
              <div className="panel model-panel">
                <ModelLayers model={bundle.model} scene={scene} active={modelKey} onActive={setModelKey} />
                <ModelLegend layer={modelLayer} />
                {volume && <SubsurfacePanel volume={volume} scene={scene} />}
              </div>) }] : []),
            ...(event ? [{ key: "events", label: "Events", icon: "rain", node: <EventsPanel event={event} /> }] : []),
            { key: "help", label: "Help", icon: "help", node: (
              <HelpPanel bundle={bundle}><Attribution bundle={bundle} sensors={!!sensorLegend} mass={!!mass} reloc={!!reloc} /></HelpPanel>) },
          ]} />
          <GoTo majors={bundle.majors} active={active} onPlace={k => { setActive(k); scene.flyTo(k); }} onSite={s => openSite(s, scene)} />
          {modelLayer?.values && <ModelReadout scene={scene} model={bundle.model} layer={modelLayer} box={bundle.overviewBox} />}
          <Tooltip hover={hover} notes={sens?.notes} />
          {sens && <SensorTip scene={scene} points={sens.points} />}
          {mass && <MassTip scene={scene} points={mass.points} doc={mass.doc} />}
          <MobileDock sheet={sheet} onSheet={setSheet} has={{ model: !!bundle.model, quakes: !!(bundle.quakes || reloc), mass: !!massLegend, events: !!event }} />
          <NavPad scene={scene} onHelp={openHelp} />
          <HelpHint onHelp={openHelp} hidden={helpOpened} />
          {site && <StationPanel site={site} bundle={bundle} notes={sens?.notes} onFly={s => scene.flyToSite(s)}
            onClose={() => { setSiteId(null); layerRef.current?.setSelected(null); }} />}
        </>
      )}
    </>
  );
}
