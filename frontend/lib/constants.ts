export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const UPLOAD_POLL_INTERVAL_MS = 2_000;
export const DASHBOARD_STALE_MS      = 5 * 60_000;
export const MAX_FILE_SIZE_BYTES     = 50 * 1024 * 1024;

export const ACCEPTED_FILE_TYPES = {
  "text/csv":                                                          [".csv"],
  "application/vnd.ms-excel":                                          [".xls"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/xml":                                                   [".xml"],
  "text/xml":                                                          [".xml"],
};

export const SEGMENT_COLORS: Record<string, string> = {
  champions: "#E8651A",
  loyal:     "#F9A826",
  at_risk:   "#EF4444",
  lost:      "#94A3B8",
  promising: "#2D6A4F",
  new:       "#1B4332",
};

export const SEVERITY_COLORS = {
  HIGH:   "#EF4444",
  MEDIUM: "#F59E0B",
  LOW:    "#3B82F6",
} as const;
