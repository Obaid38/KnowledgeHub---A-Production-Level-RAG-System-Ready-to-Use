"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import { ApexOptions } from "apexcharts";
import { useQueryVolumeQuery } from "@/hooks/queries/useDashboardQuery";
import type { QueryVolumePeriod } from "@/services/dashboard.service";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

// ─── Component ────────────────────────────────────────────────────────────────

export function QueryVolumeChart() {
  const t = useTranslations("dashboard.queryVolume");
  const [filter, setFilter] = useState<QueryVolumePeriod>("daily");

  const { data, isLoading } = useQueryVolumeQuery(filter);

  const categories = data?.categories ?? [];
  const documents  = data?.documents  ?? [];
  const queries    = data?.queries    ?? [];

  const options: ApexOptions = {
    chart: {
      fontFamily: "Outfit, sans-serif",
      height: 280,
      type: "area",
      toolbar: { show: false },
      animations: {
        enabled: true,
        speed: 400,
      },
    },
    colors: ["#2F65A7", "#36bffa"], // brand-500 + blue-light-400
    stroke: {
      curve: "smooth",
      width: [2, 2],
    },
    fill: {
      type: "gradient",
      gradient: {
        opacityFrom: 0.35,
        opacityTo: 0,
      },
    },
    legend: {
      show: true,
      position: "top",
      horizontalAlign: "right",
      fontFamily: "Outfit, sans-serif",
      fontSize: "13px",
      markers: { size: 6 },
      itemMargin: { horizontal: 12 },
    },
    markers: {
      size: 0,
      strokeColors: "#fff",
      strokeWidth: 2,
      hover: { size: 5 },
    },
    dataLabels: { enabled: false },
    grid: {
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
      borderColor: "#f2f4f7",
    },
    tooltip: {
      enabled: true,
      shared: true,
      intersect: false,
      x: { show: true },
    },
    xaxis: {
      type: "category",
      categories,
      axisBorder: { show: false },
      axisTicks: { show: false },
      labels: {
        style: { fontSize: "12px", colors: "#667085", fontFamily: "Outfit, sans-serif" },
      },
      tooltip: { enabled: false },
    },
    yaxis: {
      labels: {
        style: { fontSize: "12px", colors: "#667085", fontFamily: "Outfit, sans-serif" },
      },
      title: { text: "", style: { fontSize: "0px" } },
    },
  };

  const series = [
    { name: t("documents"), data: documents },
    { name: t("queries"),   data: queries   },
  ];

  const filters: QueryVolumePeriod[] = ["daily", "weekly", "monthly"];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white px-5 pb-5 pt-5 dark:border-gray-800 dark:bg-white/3 sm:px-6 sm:pt-6">
      {/* Header */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3>{t("title")}</h3>
          <p className="mt-0.5">{t("subtitle")}</p>
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-0.5 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-800 self-start">
          {filters.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`h-8 rounded-md px-4 text-theme-xs font-medium capitalize transition-all ${
                filter === f
                  ? "bg-white text-gray-900 shadow-theme-xs dark:bg-gray-700 dark:text-white"
                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
              }`}
            >
              {t(f)}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="max-w-full overflow-x-auto custom-scrollbar">
        <div className="min-w-[480px]">
          {isLoading ? (
            <div className="flex h-[280px] items-center justify-center">
              <span className="text-theme-sm text-gray-400 dark:text-gray-500">Loading chart…</span>
            </div>
          ) : (
            <Chart options={options} series={series} type="area" height={280} />
          )}
        </div>
      </div>
    </div>
  );
}