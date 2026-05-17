"use client";

import React from "react";
import { ResourceGauge } from "@/types/monitoring.types";
import { CircularGauge } from "./CircularGauge";

interface ResourceGaugesCardProps {
  gauges: ResourceGauge[];
}

export function ResourceGaugesCard({ gauges }: ResourceGaugesCardProps) {
  if (gauges.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-gray-200 bg-white p-10 dark:border-gray-800 dark:bg-white/[0.03]">
        <p className="text-theme-sm text-gray-400 dark:text-gray-500">No resource data available</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {gauges.map((g) => (
        <div
          key={g.id}
          className="flex items-center justify-center rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]"
        >
          <CircularGauge value={g.value} label={g.label} />
        </div>
      ))}
    </div>
  );
}