"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { qaConfig } from "@/config/companyProfile";

interface QAEmptyStateProps {
  onPromptSelect: (prompt: string) => void;
}

export function QAEmptyState({ onPromptSelect }: QAEmptyStateProps) {
  const t = useTranslations("qa.chat");

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-12">
      {/* Icon */}
      <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 dark:bg-brand-500/[0.12]">
        <svg className="h-7 w-7 text-brand-500 dark:text-brand-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>

      <h3 className="mb-1">{t("emptyTitle")}</h3>
      <p className="mb-8 text-center max-w-xs">{t("emptySubtitle")}</p>

      {/* Suggested prompts */}
      <div className="w-full max-w-lg space-y-2">
        <p className="mb-3 text-theme-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
          {t("tryAsking")}
        </p>
        {qaConfig.suggested_prompts.map((prompt) => {
          return (
            <button
              key={prompt}
              onClick={() => onPromptSelect(prompt)}
              className="group flex w-full items-center gap-3 rounded-xl border border-gray-100 bg-white px-4 py-3 text-left text-theme-sm text-gray-700 shadow-theme-xs transition-all hover:border-brand-200 hover:shadow-theme-md dark:border-white/[0.05] dark:bg-white/[0.03] dark:text-gray-300 dark:hover:border-brand-500/30"
            >
              <svg className="h-4 w-4 shrink-0 text-gray-300 group-hover:text-brand-400 dark:text-gray-600 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              {prompt}
            </button>
          );
        })}
      </div>
    </div>
  );
}
