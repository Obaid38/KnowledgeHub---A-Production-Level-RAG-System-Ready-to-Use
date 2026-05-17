"use client";

import React, { useRef, useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Spinner } from "@/helpers/document.helpers";
import { ACCEPTED_TYPES } from "@/constants/document.contants";

interface UploadZoneProps {
  onFilesSelected: (files: File[]) => void;
  uploading: boolean;
}

export function UploadZone({ onFilesSelected, uploading }: UploadZoneProps) {
  const t        = useTranslations("documents.uploadZone");
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length) onFilesSelected(files);
    },
    [onFilesSelected],
  );

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !uploading && inputRef.current?.click()}
      className={`relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 cursor-pointer transition-all duration-200
        ${dragging
          ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10"
          : "border-gray-200 bg-gray-50 hover:border-brand-400 hover:bg-brand-50/50 dark:border-gray-700 dark:bg-gray-800/50 dark:hover:border-brand-500"
        }
        ${uploading ? "pointer-events-none opacity-60" : ""}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_TYPES}
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length) onFilesSelected(files);
          e.target.value = "";
        }}
      />

      {/* folder icon */}
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-yellow-400 shadow-theme-md">
        <svg className="h-7 w-7 text-white" fill="currentColor" viewBox="0 0 24 24">
          <path d="M10 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V8a2 2 0 00-2-2h-8l-2-2z" />
        </svg>
      </div>

      {uploading ? (
        <div className="flex items-center gap-2 text-brand-500">
          <Spinner />
          <span className="text-theme-sm font-medium">{t("uploading")}</span>
        </div>
      ) : (
        <>
          <p className="text-theme-sm text-gray-500 dark:text-gray-400">
            <span className="font-semibold text-brand-500 hover:underline">{t("clickToUpload")}</span>
            {" "}{t("dragAndDrop")}
          </p>
          <p className="text-theme-xs text-gray-400">{t("hint")}</p>
        </>
      )}
    </div>
  );
}