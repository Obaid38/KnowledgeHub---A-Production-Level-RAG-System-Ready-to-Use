"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { FileText, HelpCircle, RefreshCw, Zap, Mail, ChevronDown } from "lucide-react";
import { useActivityFeedQuery } from "@/hooks/queries/useDashboardQuery";
import { getSocket } from "@/lib/socket";
import type { ActivityFeedItem, ActivityType } from "@/services/dashboard.service";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTimeAgo(timestamp: string): string {
  const diff = Math.round((Date.now() - new Date(timestamp).getTime()) / 1000);
  if (diff < 60)  return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ─── Icon per activity type ───────────────────────────────────────────────────

function ActivityIcon({ type }: { type: ActivityType }) {
  const base = "flex h-8 w-8 shrink-0 items-center justify-center rounded-full";

  if (type === "upload") return (
    <span className={`${base} bg-brand-50 dark:bg-brand-500/10`}>
      <FileText className="h-4 w-4 text-brand-500" strokeWidth={2} />
    </span>
  );
  if (type === "query") return (
    <span className={`${base} bg-blue-light-50 dark:bg-blue-light-500/10`}>
      <HelpCircle className="h-4 w-4 text-blue-light-500" strokeWidth={2} />
    </span>
  );
  if (type === "processing") return (
    <span className={`${base} bg-orange-50 dark:bg-orange-500/10`}>
      <RefreshCw className="h-4 w-4 text-orange-500" strokeWidth={2} />
    </span>
  );
  if (type === "graph") return (
    <span className={`${base} bg-success-50 dark:bg-success-500/10`}>
      <Zap className="h-4 w-4 text-success-500" strokeWidth={2} />
    </span>
  );
  return (
    <span className={`${base} bg-gray-100 dark:bg-gray-700`}>
      <Mail className="h-4 w-4 text-gray-500" strokeWidth={2} />
    </span>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function ActivityFeed() {
  const t = useTranslations("dashboard.activityFeed");

  const { data: initialActivities, isLoading } = useActivityFeedQuery();
  const [activities, setActivities] = useState<ActivityFeedItem[]>([]);

  // Seed state from API once loaded
  useEffect(() => {
    if (initialActivities) {
      setActivities(initialActivities);
    }
  }, [initialActivities]);

  // Subscribe to real-time activity events via Socket.IO
  useEffect(() => {
    const socket = getSocket();
    if (!socket.connected) socket.connect();

    const onActivity = (item: ActivityFeedItem) => {
      setActivities((prev) => {
        // Deduplicate by id and keep newest 20
        const filtered = prev.filter((a) => a.id !== item.id);
        return [item, ...filtered].slice(0, 20);
      });
    };

    socket.on("activity:feed", onActivity);
    return () => { socket.off("activity:feed", onActivity); };
  }, []);

  return (
    <div className="flex flex-col rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]" style={{ height: "416px" }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4 dark:border-white/[0.05]">
        <h3>{t("title")}</h3>
      </div>

      {/* Feed list — scrollable */}
      <div className="flex-1 overflow-y-auto custom-scrollbar divide-y divide-gray-100 dark:divide-white/[0.05]">
        {isLoading ? (
          <div className="flex items-center justify-center py-10">
            <span className="text-theme-sm text-gray-400 dark:text-gray-500">Loading…</span>
          </div>
        ) : activities.length === 0 ? (
          <div className="flex items-center justify-center py-10">
            <span className="text-theme-sm text-gray-400 dark:text-gray-500">No recent activity</span>
          </div>
        ) : (
          activities.map((item) => (
            <div key={item.id} className="flex items-start gap-3 px-5 py-3.5">
              <ActivityIcon type={item.type} />
              <div className="min-w-0 flex-1">
                <p className="text-theme-sm text-gray-700 dark:text-gray-300 leading-snug">
                  {item.text}
                </p>
                <span className="mt-0.5 block text-theme-xs text-gray-400">
                  {formatTimeAgo(item.timestamp)}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Scroll hint arrow */}
      <div className="flex justify-center border-t border-gray-100 py-2 dark:border-white/[0.05]">
        <ChevronDown className="h-4 w-4 text-gray-300 dark:text-gray-600" strokeWidth={2} />
      </div>
    </div>
  );
}