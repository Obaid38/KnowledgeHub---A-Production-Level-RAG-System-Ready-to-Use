import React, { ReactNode } from "react";
import Badge from "@/components/ui/badge/Badge";
import { ArrowUpIcon, ArrowDownIcon } from "@/icons";

// ─── Types ────────────────────────────────────────────────────────────────────

export type MetricChangeType = "success" | "error" | "neutral";

export interface MetricCardProps {
  /** Icon to display in the top-left card section */
  icon: ReactNode;
  /** Metric label (e.g. "Total Documents") */
  label: string;
  /** Primary value (e.g. "1,284" or "91%") */
  value: string | number;
  /**
   * Change badge text — pass undefined to hide the badge entirely
   * e.g. "+47 this week"
   */
  change?: string;
  /** Controls badge color and arrow direction */
  changeType?: MetricChangeType;
  /**
   * Optional plain subtitle shown below the value instead of (or alongside) a badge.
   * e.g. "Documents in queue"
   */
  subtitle?: string;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function MetricCard({
  icon,
  label,
  value,
  change,
  changeType = "neutral",
  subtitle,
}: MetricCardProps) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] md:p-6">
      {/* Icon */}
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gray-100 dark:bg-gray-800">
        {icon}
      </div>

      {/* Body */}
      <div className="mt-5 flex items-end justify-between">
        <div>
          <span className="text-theme-sm text-gray-500 dark:text-gray-400">
            {label}
          </span>
          <h4 className="mt-2 text-title-sm font-bold text-gray-800 dark:text-white/90">
            {value}
          </h4>
          {subtitle && (
            <p className="mt-0.5 text-theme-xs text-gray-400 dark:text-gray-500">
              {subtitle}
            </p>
          )}
        </div>

        {/* Change badge — only shown when `change` is provided */}
        {change && changeType !== "neutral" && (
          <Badge color={changeType === "success" ? "success" : "error"}>
            {changeType === "success" ? (
              <ArrowUpIcon className="size-3" />
            ) : (
              <ArrowDownIcon className="size-3 text-error-500" />
            )}
            {change}
          </Badge>
        )}

        {/* Neutral pill — for counts that are neither good nor bad */}
        {change && changeType === "neutral" && (
          <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-theme-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
            {change}
          </span>
        )}
      </div>
    </div>
  );
}