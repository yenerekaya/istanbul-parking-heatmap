const ISPARK_API = "https://api.ibb.gov.tr/ispark";

export interface IsparkPark {
  parkID: number;
  parkName: string;
  locationName: string;
  lat: string;
  lng: string;
  capacity: number;
  emptyCapacity: number;
  updateDate: string;
  workHours: string;
  parkType: string;
  freeTime: number;
  district: string;
  address: string;
  areaPolygon?: string;
  tariff?: string;
  monthlyFee?: number;
}

export async function fetchAllParks(): Promise<IsparkPark[]> {
  const res = await fetch(`${ISPARK_API}/Park`);
  if (!res.ok) throw new Error(`İSPARK API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function fetchParkDetail(id: number): Promise<IsparkPark> {
  const res = await fetch(`${ISPARK_API}/ParkDetay?id=${id}`);
  if (!res.ok) throw new Error(`İSPARK API ${res.status}: ${res.statusText}`);
  const data = await res.json();
  return Array.isArray(data) ? data[0] : data;
}
