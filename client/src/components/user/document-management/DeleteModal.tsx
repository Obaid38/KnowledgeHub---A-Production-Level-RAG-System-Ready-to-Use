"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { Spinner } from "@/helpers/document.helpers";
import Modal from "@/components/ui/modal";

interface DeleteModalProps {
  count: number;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}

export function DeleteModal({ count, onConfirm, onCancel, loading }: DeleteModalProps) {
  const t = useTranslations("documents.deleteModal");

  return (
    <Modal
      isOpen={true}
      onClose={onCancel}
      closeOnBackdrop={!loading}
      showCloseButton={!loading}
    >
      {/* Icon */}
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-error-50 dark:bg-error-500/10">
        <svg className="h-6 w-6 text-error-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </div>

      <h3 className="mb-2 pr-8">
        {count === 1 ? t("title", { count: 1 }) : t("titlePlural", { count })}
      </h3>
      <p className="mb-6">
        {count === 1 ? t("message") : t("messagePlural")}
      </p>

      <div className="flex gap-3">
        <button
          onClick={onCancel}
          disabled={loading}
          className="flex-1 rounded-lg border border-gray-200 bg-white py-2.5 text-theme-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
        >
          {t("cancel")}
        </button>
        <button
          onClick={onConfirm}
          disabled={loading}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-error-500 py-2.5 text-theme-sm font-medium text-white hover:bg-error-600 disabled:opacity-70"
        >
          {loading && <Spinner />}
          {t("confirm")}
        </button>
      </div>
    </Modal>
  );
}