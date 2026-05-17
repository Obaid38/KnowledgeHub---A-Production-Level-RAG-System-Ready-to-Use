"use client";

import React from "react";
import { useTranslations } from "next-intl";
import {
  useResourceGaugesQuery,
  useServiceHealthQuery,
  usePerformanceMetricsQuery,
} from "@/hooks/queries/useMonitoringQuery";
import { ResourceGaugesCard } from "./ResourceGuageCard";
import { ServiceHealthCard } from "./ServiceHealthCard";
import { PerformanceMetricsCard } from "./PerformanceMetricsCard";
import { useQueryClient } from "@tanstack/react-query";

export default function SystemMonitoring() {
  const t  = useTranslations("monitoring");
  const qc = useQueryClient();

  // React Query auto-polls every 30 s via refetchInterval
  const gaugesQuery  = useResourceGaugesQuery();
  const servicesQuery = useServiceHealthQuery();
  const metricsQuery  = usePerformanceMetricsQuery();

  const refreshing =
    gaugesQuery.isFetching || servicesQuery.isFetching || metricsQuery.isFetching;

  const handleRefresh = () => {
    qc.invalidateQueries({ queryKey: ["monitoring"] });
  };

  const gauges   = gaugesQuery.data   ?? [];
  const services = servicesQuery.data ?? [];
  const metrics  = metricsQuery.data  ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1>{t("title")}</h1>
        <p>{t("subtitle")}</p>
      </div>

      <ResourceGaugesCard gauges={gauges} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ServiceHealthCard
          services={services}
          onRefresh={handleRefresh}
          refreshing={refreshing}
        />
        <PerformanceMetricsCard metrics={metrics} />
      </div>
    </div>
  );
}
