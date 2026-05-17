// src/services/dashboard.service.ts
import { privateAxios } from "@/lib/axios";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DashboardMetrics {
  totalDocuments: { value: number; changeCount: number };
  aiQueries:      { value: number; changePct: number };
  processingCount:{ value: number };
  confidenceScore:{ value: number; changePct: number };
}

export type RecentQueryType = "Retrieval" | "Semantic" | "Keyword" | "Hybrid";

export interface RecentQuery {
  id:       string;
  question: string;
  type:     RecentQueryType;
  time:     string;
}

export type QueryVolumePeriod = "daily" | "weekly" | "monthly";

export interface QueryVolumeData {
  categories: string[];
  documents:  number[];
  queries:    number[];
}

export type ActivityType = "upload" | "query" | "processing" | "graph" | "email";

export interface ActivityFeedItem {
  id:        string;
  type:      ActivityType;
  text:      string;
  timestamp: string;
}

// ─── Service functions ────────────────────────────────────────────────────────

/** GET /dashboard/metrics */
export async function apiGetDashboardMetrics(): Promise<DashboardMetrics> {
  const { data } = await privateAxios.get<DashboardMetrics>("/dashboard/metrics");
  return data;
}

/**
 * GET /dashboard/recent-queries
 * Backend returns { queries: [{ _id, question, type, time }] }
 */
export async function apiGetRecentQueries(): Promise<RecentQuery[]> {
  const { data } = await privateAxios.get<{ queries: Array<{ _id: string; question: string; type: string; time: string }> }>(
    "/dashboard/recent-queries",
  );
  return (data.queries ?? []).map((q) => ({
    id:       q._id,
    question: q.question,
    type:     (q.type as RecentQueryType) ?? "Retrieval",
    time:     q.time,
  }));
}

/** GET /dashboard/query-volume?period=daily|weekly|monthly */
export async function apiGetQueryVolume(period: QueryVolumePeriod): Promise<QueryVolumeData> {
  const { data } = await privateAxios.get<QueryVolumeData>("/dashboard/query-volume", {
    params: { period },
  });
  return data;
}

/** GET /dashboard/activity-feed */
export async function apiGetActivityFeed(): Promise<ActivityFeedItem[]> {
  const { data } = await privateAxios.get<{ activities: ActivityFeedItem[] }>(
    "/dashboard/activity-feed",
  );
  return data.activities ?? [];
}
