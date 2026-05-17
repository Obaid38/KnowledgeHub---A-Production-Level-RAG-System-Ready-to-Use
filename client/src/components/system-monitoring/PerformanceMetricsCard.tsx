"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { PerformanceMetric } from "@/types/monitoring.types";

interface PerformanceMetricsCardProps {
  metrics: PerformanceMetric[];
}

export function PerformanceMetricsCard({ metrics }: PerformanceMetricsCardProps) {
  const t = useTranslations("monitoring.performance");

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/[0.05] dark:bg-white/[0.03]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4 dark:border-white/[0.05]">
        <h2 className="text-base">{t("title")}</h2>
        <span className="rounded-full bg-success-50 px-3 py-1 text-theme-xs font-medium text-success-500 dark:bg-success-500/10">
          {t("withinTargets")}
        </span>
      </div>

      {/* Metric rows */}
      <ul className="divide-y divide-gray-100 dark:divide-white/[0.05]">
        {metrics.length === 0 && (
          <li className="px-5 py-8 text-center text-theme-sm text-gray-400 dark:text-gray-500">
            No performance data available
          </li>
        )}
        {metrics.map((m) => (
          <li
            key={m.id}
            className="flex items-center justify-between px-5 py-3.5 hover:bg-gray-50/50 dark:hover:bg-white/[0.02] transition-colors"
          >
            {/* Label */}
            <span className="text-theme-sm text-gray-600 dark:text-gray-400">
              {m.label}
            </span>

            {/* Value + target */}
            <div className="flex items-center gap-2">
              <span className="text-theme-sm font-semibold text-gray-800 dark:text-white/90">
                {m.value}
              </span>
              {m.target && (
                <span
                  className={`text-theme-xs ${
                    m.withinTarget
                      ? "text-success-500"
                      : "text-error-500"
                  }`}
                >
                  ({m.target})
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}