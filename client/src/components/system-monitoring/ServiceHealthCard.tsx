"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { ServiceHealth, ServiceStatus } from "@/types/monitoring.types";

interface ServiceHealthCardProps {
  services:    ServiceHealth[];
  onRefresh:   () => void;
  refreshing:  boolean;
}

function StatusDot({ status }: { status: ServiceStatus }) {
  const colors: Record<ServiceStatus, string> = {
    healthy:  "bg-success-500",
    degraded: "bg-orange-400",
    down:     "bg-error-500",
  };
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${colors[status]} shrink-0`}
    />
  );
}

export function ServiceHealthCard({ services, onRefresh, refreshing }: ServiceHealthCardProps) {
  const t = useTranslations("monitoring.serviceHealth");

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/[0.05] dark:bg-white/[0.03]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4 dark:border-white/[0.05]">
        <h2 className="text-base">{t("title")}</h2>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-theme-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 transition-colors"
        >
          {refreshing && (
            <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          )}
          {t("refresh")}
        </button>
      </div>

      {/* Service rows */}
      <ul className="divide-y divide-gray-100 dark:divide-white/[0.05]">
        {services.length === 0 && (
          <li className="px-5 py-8 text-center text-theme-sm text-gray-400 dark:text-gray-500">
            No service data available
          </li>
        )}
        {services.map((svc) => (
          <li
            key={svc.id}
            className="flex items-center justify-between px-5 py-3.5 hover:bg-gray-50/50 dark:hover:bg-white/[0.02] transition-colors"
          >
            <div className="flex items-center gap-3">
              <StatusDot status={svc.status} />
              <span className="text-theme-sm text-gray-800 dark:text-white/90">
                {svc.name}
              </span>
            </div>
            <span
              className={`text-theme-sm font-medium ${
                svc.status === "degraded"
                  ? "text-orange-500"
                  : "text-brand-500"
              }`}
            >
              {svc.detail}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}