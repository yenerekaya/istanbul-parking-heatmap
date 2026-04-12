const DAY_NAMES = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"] as const;
const DAY_NAMES_FULL = [
  "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
] as const;

/** Short day name from ISO dow (0=Mon..6=Sun) */
export function dayName(dow: number): string {
  return DAY_NAMES[dow] ?? "?";
}

/** Full day name from ISO dow */
export function dayNameFull(dow: number): string {
  return DAY_NAMES_FULL[dow] ?? "?";
}

/** Format hour as "09:00", "14:00", etc. (24h format for Turkey) */
export function formatHour(hour: number): string {
  return `${hour.toString().padStart(2, "0")}:00`;
}

/** Format occupancy as percentage string */
export function formatOccupancy(occupancy: number, enforced = true): string {
  if (occupancy <= 0) return enforced ? "N/A" : "Boş";
  return `%${Math.round(occupancy * 100)}`;
}

/** Format time slot as "Çarşamba 14:00" */
export function formatTimeSlot(dow: number, hour: number): string {
  return `${dayNameFull(dow)} ${formatHour(hour)}`;
}
