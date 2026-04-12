/** Photon geocoder wrapper with Istanbul bounding box */

const PHOTON_URL = "https://photon.komoot.io/api";
const IST_BBOX = { west: 28.50, south: 40.80, east: 29.50, north: 41.35 };

export interface GeoResult {
  name: string;
  lat: number;
  lng: number;
  type: string; // "house", "street", "city", etc.
}

interface PhotonProperties {
  name?: string;
  street?: string;
  district?: string;
  type?: string;
  osm_value?: string;
}

interface PhotonFeature {
  geometry: { coordinates: [number, number] };
  properties: PhotonProperties;
}

const cache = new Map<string, GeoResult[]>();

export async function geocode(query: string): Promise<GeoResult[]> {
  const key = query.trim().toLowerCase();
  if (cache.has(key)) return cache.get(key)!;

  const params = new URLSearchParams({
    q: query,
    bbox: `${IST_BBOX.west},${IST_BBOX.south},${IST_BBOX.east},${IST_BBOX.north}`,
    limit: "5",
    lang: "tr",
    lat: "41.015",
    lon: "29.0",
  });

  const res = await fetch(`${PHOTON_URL}?${params}`);
  if (!res.ok) return [];

  const data = (await res.json()) as { features?: PhotonFeature[] };
  const results: GeoResult[] = (data.features ?? [])
    .filter((f) => {
      const [lng, lat] = f.geometry.coordinates;
      return lat >= IST_BBOX.south && lat <= IST_BBOX.north &&
             lng >= IST_BBOX.west && lng <= IST_BBOX.east;
    })
    .map((f) => ({
      name: buildDisplayName(f.properties),
      lat: f.geometry.coordinates[1],
      lng: f.geometry.coordinates[0],
      type: f.properties.osm_value ?? f.properties.type ?? "place",
    }));

  cache.set(key, results);
  return results;
}

function buildDisplayName(props: PhotonProperties): string {
  const parts: string[] = [];
  if (props.name) parts.push(props.name);
  if (props.street && props.street !== props.name) parts.push(props.street);
  if (props.district) parts.push(props.district);
  return parts.join(", ") || props.name || "Unknown";
}

/** Haversine distance in meters between two lat/lng points */
export function haversineMeters(
  lat1: number, lng1: number,
  lat2: number, lng2: number,
): number {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
