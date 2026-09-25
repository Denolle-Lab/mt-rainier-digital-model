import "./ui.css";

// Where the map's data come from (shown at the foot of Help).
export default function Attribution({ bundle, sensors, mass, reloc }) {
  return (
    <div className="attribution">Terrain and imagery: USGS 3DEP and The National Map (public domain), 1 m lidar at the summit. Stations: EarthScope FDSN, active as of {bundle.stations.asOf}{sensors ? "; other sensors: rainier3d inventory (UW 2025 nodes, EarthScope GNSS, Synoptic, past FDSN deployments, DAS)" : ""}.{bundle.quakes ? " Earthquakes: USGS ComCat (PNSN), depth below sea level." : ""}{mass ? " Mass movements: Washington Geological Survey landslide inventory and 1:100,000 geology, Allstadt et al. (2017)." : ""}{reloc ? " Relocated earthquakes: rainier3d S26 (NonLinLoc, PNSN picks)." : ""}</div>
  );
}
