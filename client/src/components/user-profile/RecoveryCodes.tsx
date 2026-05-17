"use client";
import React, { useState } from "react";
import { useTranslations } from "next-intl";

// ── Props ──────────────────────────────────────────────────────────────────
interface RecoveryCodesProps {
  codes:    string[];
  onDone:   () => void;        // called when user clicks "I have saved my codes"
}

// ── Component ──────────────────────────────────────────────────────────────
export function RecoveryCodes({ codes, onDone }: RecoveryCodesProps) {
  const t = useTranslations("profile.mfa.modal");

  const [allCopied,    setAllCopied]    = useState(false);
  const [downloaded,   setDownloaded]   = useState(false);
  const [confirmed,    setConfirmed]    = useState(false);

  // ── Copy all codes to clipboard ──────────────────────────────────────────
  const handleCopyAll = async () => {
    await navigator.clipboard.writeText(codes.join("\n"));
    setAllCopied(true);
    setTimeout(() => setAllCopied(false), 2000);
  };

  // ── Download as plain .txt — pure browser Blob, no server needed ─────────
  const handleDownload = () => {
    const lines = [
      "Recovery Codes",
      "==============",
      "",
      "Keep these somewhere safe. Each code can only be used once.",
      "If you run out, regenerate them from your profile settings.",
      "",
      ...codes.map((c, i) => `${String(i + 1).padStart(2, "0")}. ${c}`),
      "",
      `Generated: ${new Date().toUTCString()}`,
    ].join("\n");

    const blob = new Blob([lines], { type: "text/plain" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = "recovery-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
    setDownloaded(true);
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div>
      {/* Header */}
      <div className="pr-10 mb-5">
        <h3 className="mb-1">{t("codesTitle")}</h3>
        <p>{t("codesSubtitle")}</p>
      </div>

      {/* Warning banner */}
      <div className="flex items-start gap-3 rounded-xl border border-orange-200 bg-orange-50 dark:border-orange-500/20 dark:bg-orange-500/10 px-4 py-3 mb-5">
        <svg
          className="h-5 w-5 shrink-0 text-orange-500 mt-0.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
          />
        </svg>
        <p className="text-theme-xs text-orange-700 dark:text-orange-300 leading-relaxed">
          {t("codesWarning")}
        </p>
      </div>

      {/* Code grid */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        {codes.map((code, i) => (
          <code
            key={i}
            className="font-mono text-theme-sm bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2.5 text-center tracking-widest border border-gray-200 dark:border-gray-700 text-gray-800 dark:text-white/90 select-all cursor-text"
          >
            {code}
          </code>
        ))}
      </div>

      {/* Remaining count hint */}
      <p className="text-theme-xs text-gray-400 dark:text-gray-500 text-right mb-4">
        {t("codesCount", { count: codes.length })}
      </p>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2 mb-5">
        <button
          type="button"
          onClick={handleCopyAll}
          className="btn-outline lg:w-auto text-theme-sm flex items-center gap-2"
        >
          {allCopied ? (
            <>
              <svg className="h-4 w-4 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              {t("copied")}
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              {t("copyAll")}
            </>
          )}
        </button>

        <button
          type="button"
          onClick={handleDownload}
          className={`btn-outline lg:w-auto text-theme-sm flex items-center gap-2 ${
            downloaded
              ? "border-success-300 text-success-600 dark:border-success-500/30 dark:text-success-400"
              : ""
          }`}
        >
          {downloaded ? (
            <>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              {t("downloaded")}
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {t("download")}
            </>
          )}
        </button>
      </div>

      {/* Confirmation checkbox — user must tick before Done unlocks */}
      <label className="flex items-start gap-3 cursor-pointer mb-5 group">
        <div className="relative mt-0.5">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            className="sr-only peer"
          />
          <div className="h-4 w-4 rounded border border-gray-300 bg-white dark:border-gray-600 dark:bg-gray-800 peer-checked:border-brand-500 peer-checked:bg-brand-500 transition-colors" />
          <svg
            className="absolute inset-0 h-4 w-4 text-white opacity-0 peer-checked:opacity-100 transition-opacity pointer-events-none"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <span className="text-theme-xs text-gray-600 dark:text-gray-400 leading-relaxed group-hover:text-gray-800 dark:group-hover:text-gray-200 transition-colors">
          {t("codesConfirmLabel")}
        </span>
      </label>

      {/* Done button — locked until checkbox is ticked */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onDone}
          disabled={!confirmed}
          className="btn-primary lg:w-auto disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {t("done")}
        </button>
      </div>

      {!confirmed && (
        <p className="text-theme-xs text-gray-400 dark:text-gray-500 text-right mt-2">
          {t("doneHint")}
        </p>
      )}
    </div>
  );
}