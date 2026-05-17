// ── Resource gauge ────────────────────────────────────────────────────────────
export interface ResourceGauge {
  id:    string;
  label: string;
  value: number;          // 0–100
  unit:  string;          // e.g. "%" 
}

// ── Service health row ────────────────────────────────────────────────────────
export type ServiceStatus = "healthy" | "degraded" | "down";

export interface ServiceHealth {
  id:     string;
  name:   string;
  status: ServiceStatus;
  detail: string;         // e.g. "12ms avg query"
}

// ── Performance metric row ────────────────────────────────────────────────────
export interface PerformanceMetric {
  id:         string;
  label:      string;
  value:      string;     // e.g. "6.4s"
  target:     string;     // e.g. "target <10s ✓"
  withinTarget: boolean;
}