"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import { DocumentCategory } from "@/types/documents";
import { CATEGORIES } from "@/constants/document.contants";
import { Spinner } from "@/helpers/document.helpers";
import Modal from "@/components/ui/modal";

interface UploadModalProps {
  files: File[];
  onConfirm: (category: DocumentCategory | null) => void;
  onCancel: () => void;
  uploading: boolean;
}

export function UploadModal({ files, onConfirm, onCancel, uploading }: UploadModalProps) {
  const t = useTranslations("documents.uploadModal");
  const [category, setCategory] = useState<DocumentCategory | null>(null);

  return (
    <Modal
      isOpen={true}
      onClose={onCancel}
      closeOnBackdrop={!uploading}
      showCloseButton={!uploading}
    >
      <h3 className="mb-1 pr-8">{t("title")}</h3>
      <p className="mb-5">
        {files.length === 1
          ? t("subtitle", { count: 1 })
          : t("subtitlePlural", { count: files.length })}
      </p>

      {/* File list */}
      <div className="mb-5 max-h-40 overflow-y-auto rounded-lg border border-gray-100 bg-gray-50 custom-scrollbar dark:border-gray-700 dark:bg-gray-800">
        {files.map((f, i) => (
          <div key={i} className="flex items-center justify-between px-3 py-2">
            <span className="truncate text-theme-sm text-gray-700 dark:text-gray-300">
              {f.name}
            </span>
            <span className="ml-3 shrink-0 text-theme-xs text-gray-400">
              {(f.size / 1024 / 1024).toFixed(1)} MB
            </span>
          </div>
        ))}
      </div>

      {/* Category selector */}
      <div className="mb-6">
        <label className="mb-1.5 block">
          {t("categoryLabel")}{" "}
          <span className="font-normal text-gray-400">{t("categoryOptional")}</span>
        </label>
        <select
          value={category ?? ""}
          onChange={(e) => setCategory((e.target.value as DocumentCategory) || null)}
          className="form-input"
        >
          <option value="">{t("categoryPlaceholder")}</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      <div className="flex gap-3">
        <button
          onClick={onCancel}
          disabled={uploading}
          className="btn-outline flex-1 disabled:opacity-50"
        >
          {t("cancel")}
        </button>
        <button
          onClick={() => onConfirm(category)}
          disabled={uploading}
          className="btn-primary flex flex-1 items-center justify-center gap-2 disabled:opacity-70"
        >
          {uploading && <Spinner />}
          {t("upload")}
        </button>
      </div>
    </Modal>
  );
}