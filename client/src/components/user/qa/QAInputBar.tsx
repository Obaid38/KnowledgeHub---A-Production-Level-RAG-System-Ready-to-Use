"use client";

import React, { useRef, useEffect, KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import Select, { MultiValue, StylesConfig } from "react-select";
import { useTheme } from "@/context/ThemeContext";

const CATEGORY_OPTIONS = [
  { value: "sop", label: "SOP" },
  { value: "compliance", label: "Compliance" },
  { value: "finance", label: "Finance" },
  { value: "technical", label: "Technical" },
  { value: "hr", label: "HR" },
  { value: "legal", label: "Legal" },
  { value: "general", label: "General" },
  { value: "cases", label: "Cases" },
];

type CategoryOption = { value: string; label: string };

const getSelectStyles = (theme: "light" | "dark"): StylesConfig<CategoryOption, true> => {
  const isDark = theme === "dark";

  return {
    control: (base) => ({
      ...base,
      fontSize: "12px",
      backgroundColor: isDark ? "#1f2937" : "#f9fafb", // dark:bg-gray-800 / light:bg-gray-50
      borderColor: isDark ? "#374151" : "#e5e7eb",
      boxShadow: "none",
      minHeight: "32px",
    }),

    valueContainer: (base) => ({
      ...base,
      padding: "2px 8px",
      gap: "4px",
    }),

    multiValue: (base) => ({
      ...base,
      backgroundColor: isDark ? "#374151" : "#ede9fe",
      borderRadius: "6px",
      fontSize: "11px",
    }),

    multiValueLabel: (base) => ({
      ...base,
      color: isDark ? "#e5e7eb" : "#6d28d9",
      padding: "1px 4px",
    }),

    multiValueRemove: (base) => ({
      ...base,
      color: isDark ? "#d1d5db" : "#7c3aed",
      ":hover": {
        backgroundColor: isDark ? "#4b5563" : "#c4b5fd",
        color: isDark ? "#ffffff" : "#4c1d95",
      },
      borderRadius: "0 6px 6px 0",
    }),

    placeholder: (base) => ({
      ...base,
      fontSize: "12px",
      color: isDark ? "#9ca3af" : "#9ca3af",
    }),

    menu: (base) => ({
      ...base,
      fontSize: "12px",
      backgroundColor: isDark ? "#1f2937" : "#f9fafb",
      zIndex: 50,
    }),

    menuList: (base) => ({
      ...base,
      maxHeight: "200px",
      overflowY: "auto",
      paddingTop: 0,
      paddingBottom: 0,
    }),

    option: (base, state) => ({
      ...base,
      backgroundColor: state.isSelected
        ? isDark
          ? "#374151"
          : "#ede9fe"
        : state.isFocused
        ? isDark
          ? "#2d3748"
          : "#f3f4f6"
        : isDark
        ? "#1f2937"
        : "#f9fafb",
      color: isDark ? "#e5e7eb" : "#374151",
      cursor: "pointer",
      paddingTop: "6px",
      paddingBottom: "6px",
    }),

    dropdownIndicator: (base) => ({
      ...base,
      padding: "4px",
      color: isDark ? "#9ca3af" : "#6b7280",
    }),

    clearIndicator: (base) => ({
      ...base,
      padding: "4px",
      color: isDark ? "#9ca3af" : "#6b7280",
    }),

    indicatorSeparator: () => ({ display: "none" }),
  };
};

interface QAInputBarProps {
  value: string;
  onChange: (val: string) => void;
  onSubmit: () => void;
  loading: boolean;
  selectedCategories: string[];
  onCategoriesChange: (categories: string[]) => void;
}

export function QAInputBar({
  value,
  onChange,
  onSubmit,
  loading,
  selectedCategories,
  onCategoriesChange,
}: QAInputBarProps) {
  const t = useTranslations("qa.chat");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
const { theme } = useTheme();
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [value]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!loading && value.trim()) onSubmit();
    }
  };

  const handleCategoryChange = (selected: MultiValue<CategoryOption>) => {
    onCategoriesChange(selected.map((o) => o.value));
  };

  const selectedOptions = CATEGORY_OPTIONS.filter((o) =>
    selectedCategories.includes(o.value),
  );

  return (
    <div className="border-t border-gray-100 bg-white px-4 py-3 dark:border-white/[0.05] dark:bg-gray-900">
      <div className="flex items-end gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 shadow-theme-xs transition-all focus-within:border-brand-400 focus-within:shadow-focus-ring dark:border-gray-700 dark:bg-gray-800">
        
        {/* TEXTAREA (LEFT) */}
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("inputPlaceholder")}
          disabled={loading}
          className="flex-1 resize-none bg-transparent text-theme-sm text-gray-800 placeholder-gray-400 focus:outline-none disabled:opacity-60 dark:text-white/90 dark:placeholder-gray-500 leading-relaxed"
          style={{ minHeight: "24px", maxHeight: "140px" }}
        />

        {/* CATEGORY DROPDOWN (RIGHT) */}
        {/* <div className="w-44 shrink-0">
          <Select
            isMulti
            options={CATEGORY_OPTIONS}
            value={selectedOptions}
            onChange={handleCategoryChange}
            styles={getSelectStyles(theme)}
            placeholder={t("selectCategories") || "Categories"}
            maxMenuHeight={200}
            classNamePrefix="qa-select"
            isDisabled={loading}
            closeMenuOnSelect={false}
            isClearable={true}
            menuPortalTarget={
              typeof window !== "undefined" ? document.body : null
            }
            menuPosition="fixed"
          />
        </div> */}

        {/* SEND BUTTON */}
        <button
          onClick={onSubmit}
          disabled={loading || !value.trim()}
          className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-500 text-white transition-all hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
          ) : (
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          )}
        </button>
      </div>

      {/* FOOTER TEXT */}
      <p className="mt-1.5 text-center text-theme-xs text-gray-400 dark:text-gray-600">
        {t("pressEnter")}{" "}
        <kbd className="rounded border border-gray-200 px-1 py-0.5 font-mono text-[10px] dark:border-gray-700">
          Enter
        </kbd>{" "}
        {t("toSend")}{" "}
        <kbd className="rounded border border-gray-200 px-1 py-0.5 font-mono text-[10px] dark:border-gray-700">
          {t("shiftEnter")}
        </kbd>{" "}
        {t("forNewLine")}
      </p>
    </div>
  );
}