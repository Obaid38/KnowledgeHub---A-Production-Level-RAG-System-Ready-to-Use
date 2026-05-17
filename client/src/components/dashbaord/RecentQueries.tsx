"use client";

import React from "react";
import { useTranslations } from "next-intl";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Badge from "@/components/ui/badge/Badge";
import { useRecentQueriesQuery } from "@/hooks/queries/useDashboardQuery";
import { RecentQueryType } from "@/services/dashboard.service";

function queryTypeBadgeColor(type: RecentQueryType): "primary" | "info" | "warning" | "success" {
  const map: Record<RecentQueryType, "primary" | "info" | "warning" | "success"> = {
    Retrieval: "primary",
    Semantic:  "info",
    Keyword:   "warning",
    Hybrid:    "success",
  };
  return map[type] ?? "primary";
}

export function RecentQueries() {
  const t    = useTranslations("dashboard.recentQueries");
  const tCol = useTranslations("dashboard.recentQueries.columns");
  const tTyp = useTranslations("dashboard.recentQueries.types");

  const { data: queries = [], isLoading } = useRecentQueriesQuery();

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4 dark:border-white/[0.05]">
        <h3>{t("title")}</h3>
        <button className="text-theme-sm font-medium text-brand-500 hover:text-brand-600 hover:underline dark:text-brand-400">
          {t("viewAll")}
        </button>
      </div>

      <div className="overflow-x-auto custom-scrollbar">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-gray-100 dark:border-white/[0.05]">
              <TableCell isHeader className="px-5 py-3 text-left text-theme-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
                {tCol("question")}
              </TableCell>
              <TableCell isHeader className="px-5 py-3 text-left text-theme-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500 w-32">
                {tCol("type")}
              </TableCell>
              <TableCell isHeader className="px-5 py-3 text-left text-theme-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500 w-28">
                {tCol("time")}
              </TableCell>
            </TableRow>
          </TableHeader>

          <TableBody className="divide-y divide-gray-100 dark:divide-white/[0.05]">
            {isLoading ? (
              <TableRow>
                <TableCell className="px-5 py-8 text-center text-theme-sm text-gray-400 dark:text-gray-500">
                  Loading…
                </TableCell>
              </TableRow>
            ) : queries.length === 0 ? (
              <TableRow>
                <TableCell className="px-5 py-8 text-center text-theme-sm text-gray-400 dark:text-gray-500">
                  No recent queries
                </TableCell>
              </TableRow>
            ) : (
              queries.map((q) => (
                <TableRow key={q.id} className="hover:bg-gray-50/50 transition-colors dark:hover:bg-white/[0.02]">
                  <TableCell className="px-5 py-3.5">
                    <span className="text-theme-sm font-medium text-gray-800 dark:text-white/90 line-clamp-1">
                      {q.question}
                    </span>
                  </TableCell>
                  <TableCell className="px-5 py-3.5">
                    <Badge size="sm" color={queryTypeBadgeColor(q.type)}>
                      {tTyp(q.type.toLowerCase() as "retrieval" | "semantic" | "keyword" | "hybrid")}
                    </Badge>
                  </TableCell>
                  <TableCell className="px-5 py-3.5">
                    <span className="text-theme-sm text-gray-400 dark:text-gray-500">{q.time}</span>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
