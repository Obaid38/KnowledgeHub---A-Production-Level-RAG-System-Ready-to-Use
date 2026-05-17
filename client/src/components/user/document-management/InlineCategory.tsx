"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import { DocumentCategory } from  "@/types/documents";
import { CATEGORIES } from "@/constants/document.contants";
import { Spinner } from "@/helpers/document.helpers";

interface InlineCategoryEditorProps {
  docId:   string;
  current: DocumentCategory | null;
  onSave:  (id: string, category: DocumentCategory) => Promise<void>;
}

export function InlineCategoryEditor({ docId, current, onSave }: InlineCategoryEditorProps) {
  const t = useTranslations("documents.table");
  const [editing, setEditing] = useState(false);
  const [saving,  setSaving]  = useState(false);
  const [value,   setValue]   = useState<DocumentCategory | null>(current);

  const handleSave = async () => {
    if (!value) return;
    setSaving(true);
    await onSave(docId, value);
    setSaving(false);
    setEditing(false);
  };

  const handleCancel = () => {
    setEditing(false);
    setValue(current);
  };

  if (!editing) {
    return (
      <button
        onClick={() => setEditing(true)}
        className="group flex items-center gap-1.5"
        title="Click to change category"
      >
        {value ? (
          <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-theme-xs font-medium text-gray-700 transition-colors group-hover:bg-brand-50 group-hover:text-brand-600 dark:bg-gray-700 dark:text-gray-300">
            {value}
          </span>
        ) : (
          <span className="text-theme-xs text-gray-400 transition-colors group-hover:text-brand-500">
            {t("assign")}
          </span>
        )}
        <svg
          className="h-3.5 w-3.5 text-gray-400 opacity-0 transition-opacity group-hover:opacity-100"
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 112.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z" />
        </svg>
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <select
        autoFocus
        value={value ?? ""}
        onChange={(e) => setValue(e.target.value as DocumentCategory)}
        className="h-7 rounded border border-brand-400 bg-white px-2 text-theme-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:bg-gray-800 dark:text-gray-300"
      >
        <option value="">Select…</option>
        {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>

      <button
        onClick={handleSave}
        disabled={!value || saving}
        className="flex h-7 w-7 items-center justify-center rounded bg-brand-500 text-white shadow-theme-xs hover:bg-brand-600 disabled:opacity-50"
      >
        {saving ? <Spinner /> : (
          <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        )}
      </button>

      <button
        onClick={handleCancel}
        className="flex h-7 w-7 items-center justify-center rounded border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800"
      >
        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}