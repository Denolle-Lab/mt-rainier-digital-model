// Local equirectangular kilometers around the summit: x east, z south, y up (km). Same constants as data/rainier/extent.py.
export const LON0 = -121.7604, LAT0 = 46.8528;
export const KX = 111.32 * Math.cos((LAT0 * Math.PI) / 180), KZ = 111.13;
export const toX = lon => (lon - LON0) * KX;
export const toZ = lat => -(lat - LAT0) * KZ;
export const fromX = x => LON0 + x / KX;
export const fromZ = z => LAT0 - z / KZ;
