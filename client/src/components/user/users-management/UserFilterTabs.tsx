"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { UserFilterTab } from "@/types/users";
import { USER_FILTER_TABS } from "@/constants/users.constants";
interface UserFilterTabsProps {
  active:   UserFilterTab;
  counts:   Record<UserFilterTab, number>;
  onChange: (tab: UserFilterTab) => void;
}

export function UserFilterTabs({ active, counts, onChange }: UserFilterTabsProps) {
  const t = useTranslations("users.filters");

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {USER_FILTER_TABS.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          className={`inline-flex items-center gap-1.5 rounded-lg border px-4 py-2 text-theme-sm font-medium transition-colors ${
            active === tab
              ? "border-brand-500 bg-brand-500 text-white"
              : "border-gray-200 bg-white text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-brand-500 dark:hover:text-brand-400"
          }`}
        >
          {t(tab.toLowerCase() as "all" | "verified" | "unverified")}
          <span
            className={`rounded-full px-1.5 py-0.5 text-theme-xs font-semibold leading-none ${
              active === tab
                ? "bg-white/20 text-white"
                : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
            }`}
          >
            {counts[tab]}
          </span>
        </button>
      ))}
    </div>
  );
}