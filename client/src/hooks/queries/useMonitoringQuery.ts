// src/hooks/queries/useMonitoringQuery.ts
import { useQuery } from "@tanstack/react-query";
import {
  apiGetResourceGauges,
  apiGetServiceHealth,
  apiGetPerformanceMetrics,
} from "@/services/monitoring.service";

const POLL_INTERVAL = 30_000; // 30 s — matches the previous manual setInterval

/** Real-time resource gauges (CPU, RAM, Disk, GPU) — auto-refreshes every 30 s. */
export function useResourceGaugesQuery() {
  return useQuery({
    queryKey:       ["monitoring", "resources"],
    queryFn:        apiGetResourceGauges,
    staleTime:      POLL_INTERVAL,
    refetchInterval: POLL_INTERVAL,
  });
}

/** Service health (MongoDB, MinIO, etc.) — auto-refreshes every 30 s. */
export function useServiceHealthQuery() {
  return useQuery({
    queryKey:       ["monitoring", "services"],
    queryFn:        apiGetServiceHealth,
    staleTime:      POLL_INTERVAL,
    refetchInterval: POLL_INTERVAL,
  });
}

/** Performance metrics (avg latency, uptime, throughput) — auto-refreshes every 30 s. */
export function usePerformanceMetricsQuery() {
  return useQuery({
    queryKey:       ["monitoring", "performance"],
    queryFn:        apiGetPerformanceMetrics,
    staleTime:      POLL_INTERVAL,
    refetchInterval: POLL_INTERVAL,
  });
}
