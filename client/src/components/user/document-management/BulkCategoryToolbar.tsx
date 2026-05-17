"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import { DocumentCategory } from  "@/types/documents";
import { CATEGORIES } from "@/constants/document.contants";
import { Spinner } from "@/helpers/document.helpers";

interface BulkCategoryToolbarProps {
  selectedCount:    number;
  onUpdateCategory: (category: DocumentCategory) => Promise<void>;
  onDelete:         () => void;
}

export function BulkCategoryToolbar({
  selectedCount,
  onUpdateCategory,
  onDelete,
}: BulkCategoryToolbarProps) {
  const t = useTranslations("documents.bulkActions");

  const [selected, setSelected] = useState<DocumentCategory | "">("");
  const [applying, setApplying] = useState(false);

  const handleApply = async () => {
    if (!selected) return;
    setApplying(true);
    try {
      await onUpdateCategory(selected as DocumentCategory);
      setSelected(""); // reset after successful apply
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Bulk category updater */}
      <div className="flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-1.5 dark:border-brand-500/30 dark:bg-brand-500/10">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value as DocumentCategory | "")}
          className="h-7 rounded border border-brand-300 bg-white px-2 text-theme-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-brand-500/40 dark:bg-gray-800 dark:text-gray-300"
        >
          {/* ✅ t() with no interpolation needed for the placeholder */}
          <option value="">{t("selectCategory")}</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <button
          onClick={handleApply}
          disabled={!selected || applying}
          className="flex h-7 items-center gap-1.5 rounded bg-brand-500 px-3 text-theme-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50 shadow-theme-xs"
        >
          {applying && <Spinner />}
          {/* ✅ Pass count as interpolation variable — NOT .replace() */}
          {applying ? t("applying") : t("apply")}
        </button>

        {/* ✅ Correct: pass { count } as second arg to t() */}
        <span className="text-theme-xs text-brand-600 dark:text-brand-400">
          {t("updateCategory", { count: selectedCount })}
        </span>
      </div>

      {/* Bulk delete */}
      <button
        onClick={onDelete}
        className="flex items-center gap-1.5 rounded-lg border border-error-200 bg-error-50 px-3 py-1.5 text-theme-sm font-medium text-error-600 hover:bg-error-100 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-400"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
        {/* ✅ Correct interpolation */}
        {t("deleteSelected", { count: selectedCount })}
      </button>
    </div>
  );
}