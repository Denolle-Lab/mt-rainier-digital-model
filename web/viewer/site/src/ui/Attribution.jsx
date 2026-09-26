import "./ui.css";

// Where the map's data come from and under which terms (shown at the foot of Help). Each model layer names its
// sources and their licences in its own legend (layers.json, from configs/sources.yaml).
export default function Attribution({ bundle, sensors, mass, reloc, storm }) {
  return (
    <div className="attribution">
      Terrain and imagery: USGS 3DEP and The National Map (public domain), 1 m lidar at the summit. Stations: EarthScope
      FDSN, active as of {bundle.stations.asOf}{sensors ? "; other sensors: rainier3d inventory (UW 2025 nodes, EarthScope GNSS, Synoptic, past FDSN deployments, DAS)" : ""}.
      {bundle.quakes ? " Earthquakes: USGS ComCat (PNSN), public domain, depth below sea level." : ""}
      {mass ? " Mass movements: Washington Geological Survey landslide inventory and 1:100,000 geology (free use with citation), Allstadt et al. (2017)." : ""}
      {reloc ? " Relocated earthquakes: rainier3d S26 (NonLinLoc, PNSN picks)." : ""}
      {storm ? " Storm: NOAA MRMS precipitation (open data), USGS river gauges (public domain), seis-hydro-2-sed virtual discharge (MIT)." : ""}
      {" "}Model layers name their sources and licences in their legends; the water-table depth of Ma et al. (2026) is shown
      with attribution under its CC BY-NC-ND 4.0 licence and is not redistributed as data. rainier3d products: CC BY 4.0;
      viewer code: MIT.
    </div>
  );
}
