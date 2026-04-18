import type { StationData, TimeSlot } from "../types";

interface StationDetailPanelProps {
  station: StationData | null;
  timeSlot: TimeSlot;
  onClose: () => void;
}

export function StationDetailPanel({ station: _station, timeSlot: _timeSlot, onClose: _onClose }: StationDetailPanelProps) {
  return null;
}
