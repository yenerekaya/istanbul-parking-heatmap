import type { StationData, TimeSlot } from "../types";

interface StationDetailPanelProps {
  station: StationData | null;
  timeSlot: TimeSlot;
  onClose: () => void;
}

export function StationDetailPanel({ station, timeSlot, onClose }: StationDetailPanelProps) {
  return null;
}
