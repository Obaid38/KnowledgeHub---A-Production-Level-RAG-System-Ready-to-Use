// src/hooks/queries/useDashboardQuery.ts
import { useQuery } from "@tanstack/react-query";
import {
  apiGetDashboardMetrics,
  apiGetRecentQueries,
  apiGetQueryVolume,
  apiGetActivityFeed,
  type QueryVolumePeriod,
} from "@/services/dashboard.service";

/** Dashboard summary metrics (document count, AI queries, confidence, etc.) */
export function useDashboardMetricsQuery() {
  return useQuery({
    queryKey: ["dashboard", "metrics"],
    queryFn:  apiGetDashboardMetrics,
    staleTime: 60 * 1000,
  });
}

/** Five most recent Q&A queries. */
export function useRecentQueriesQuery() {
  return useQuery({
    queryKey: ["dashboard", "recent-queries"],
    queryFn:  apiGetRecentQueries,
    staleTime: 60 * 1000,
  });
}

/** Query volume time-series for the chart (daily / weekly / monthly). */
export function useQueryVolumeQuery(period: QueryVolumePeriod) {
  return useQuery({
    queryKey: ["dashboard", "query-volume", period],
    queryFn:  () => apiGetQueryVolume(period),
    staleTime: 60 * 1000,
  });
}

/** Recent system activities for the activity feed (initial load). */
export function useActivityFeedQuery() {
  return useQuery({
    queryKey: ["dashboard", "activity-feed"],
    queryFn:  apiGetActivityFeed,
    staleTime: 30 * 1000,
  });
}
