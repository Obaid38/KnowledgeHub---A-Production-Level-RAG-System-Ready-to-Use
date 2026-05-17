"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { FileText, MessageCircleQuestion, RefreshCw, BadgeCheck } from "lucide-react";
import { MetricCard } from "./MetricCard";
import { useDashboardMetricsQuery } from "@/hooks/queries/useDashboardQuery";

export function DashboardMetrics() {
  const t = useTranslations("dashboard.metrics");
  const { data, isLoading } = useDashboardMetricsQuery();

  const metrics = [
    {
      icon:        <FileText className="size-6 text-brand-500" strokeWidth={1.8} />,
      label:       t("totalDocuments"),
      value:       isLoading ? "—" : String(data?.totalDocuments.value ?? 0),
      change:      data ? t("totalDocumentsChange", { count: data.totalDocuments.changeCount }) : undefined,
      changeType:  "success" as const,
    },
    {
      icon:        <MessageCircleQuestion className="size-6 text-brand-500" strokeWidth={1.8} />,
      label:       t("aiQueries"),
      value:       isLoading ? "—" : String(data?.aiQueries.value ?? 0),
      change:      data ? t("aiQueriesChange", { pct: data.aiQueries.changePct }) : undefined,
      changeType:  "success" as const,
    },
    {
      icon:        <RefreshCw className="size-6 text-orange-500" strokeWidth={1.8} />,
      label:       t("processing"),
      value:       isLoading ? "—" : String(data?.processingCount.value ?? 0),
      subtitle:    t("processingSubtitle"),
      changeType:  "neutral" as const,
    },
    {
      icon:        <BadgeCheck className="size-6 text-success-500" strokeWidth={1.8} />,
      label:       t("confidenceScore"),
      value:       isLoading ? "—" : `${data?.confidenceScore.value ?? 0}%`,
      change:      data ? t("confidenceScoreChange", { pct: data.confidenceScore.changePct }) : undefined,
      changeType:  "success" as const,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 md:gap-6">
      {metrics.map((m) => (
        <MetricCard key={m.label} {...m} />
      ))}
    </div>
  );
}
