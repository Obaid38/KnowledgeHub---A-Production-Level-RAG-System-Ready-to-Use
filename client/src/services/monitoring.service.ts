// src/services/monitoring.service.ts
import { privateAxios } from "@/lib/axios";
import { ResourceGauge, ServiceHealth, PerformanceMetric } from "@/types/monitoring.types";

/**
 * GET /monitoring/resources
 * Returns CPU, RAM, Disk, GPU gauges.
 * Backend already returns the exact ResourceGauge[] shape.
 */
export async function apiGetResourceGauges(): Promise<ResourceGauge[]> {
  const { data } = await privateAxios.get<{ resources: ResourceGauge[] }>("/monitoring/resources");
  return data.resources ?? [];
}

/**
 * GET /monitoring/services
 * Returns MongoDB, Vector Index, MinIO and Job Queue health.
 * Backend already returns the exact ServiceHealth[] shape.
 */
export async function apiGetServiceHealth(): Promise<ServiceHealth[]> {
  const { data } = await privateAxios.get<{ services: ServiceHealth[] }>("/monitoring/services");
  return data.services ?? [];
}

/**
 * GET /monitoring/performance
 * Returns avg query time, uptime %, and throughput metrics.
 * Backend already returns the exact PerformanceMetric[] shape.
 */
export async function apiGetPerformanceMetrics(): Promise<PerformanceMetric[]> {
  const { data } = await privateAxios.get<{ metrics: PerformanceMetric[] }>("/monitoring/performance");
  return data.metrics ?? [];
}
