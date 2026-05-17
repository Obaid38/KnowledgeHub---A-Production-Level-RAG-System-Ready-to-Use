"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { QAMessage } from "@/types/qa.types";
import { ThinkingIndicator } from "./ThinkingIndicator";

interface QAMessageBubbleProps {
  message: QAMessage;
  onFeedback: (messageId: string, feedback: "helpful" | "not_helpful") => void;
  onRegenerate: (messageId: string) => void;
}

function getFileIconColor(type: string) {
  switch (type.toUpperCase()) {
    case "PDF":
      return "text-error-600 bg-error-50 dark:bg-error-500/10 dark:text-error-400";
    case "EXCEL":
    case "XLSX":
      return "text-success-600 bg-success-50 dark:bg-success-500/10 dark:text-success-400";
    case "EMAIL":
    case "EML":
      return "text-brand-600 bg-brand-50 dark:bg-brand-500/10 dark:text-brand-400";
    default:
      return "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-400";
  }
}

function SourceChip({ filename, type }: { filename: string; type: string }) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-theme-xs font-medium ${getFileIconColor(type)}`}
    >
      <svg
        className="h-3.5 w-3.5 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <span className="truncate max-w-[160px]">{filename}</span>
    </div>
  );
}

// Strip any inline "Sources:" / "**Sources**" / "---" block the backend appends to the answer
function stripInlineSources(content: string): string {
  // Find the earliest line that starts a sources block and cut everything from there
  const idx = content.search(/\n\s*(Sources\s*:|---|\*\*Sources\*\*)/i);
  return idx === -1 ? content.trimEnd() : content.slice(0, idx).trimEnd();
}

export function QAMessageBubble({
  message,
  onFeedback,
  onRegenerate,
}: QAMessageBubbleProps) {
  const tChat     = useTranslations("qa.chat");
  const tFeedback = useTranslations("qa.feedback");

  const isUser = message.role === "user";

  // ── User bubble ────────────────────────────────────────────────────────────
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%]">
          <div className="rounded-2xl rounded-br-sm bg-brand-500 px-4 py-3 text-theme-sm text-white leading-relaxed">
            {message.content}
          </div>
          <p className="mt-1 text-right text-theme-xs text-gray-400 dark:text-gray-500">
            {tChat("you")} · {message.timestamp}
          </p>
        </div>
      </div>
    );
  }

  // ── Assistant bubble ───────────────────────────────────────────────────────
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] w-full">
        <div className="rounded-2xl rounded-bl-sm border border-gray-100 bg-white px-4 py-4 shadow-theme-xs dark:border-white/[0.05] dark:bg-white/[0.03]">

          {/* While streaming → show the progressive thinking indicator */}
          {message.isStreaming ? (
            <ThinkingIndicator />
          ) : (
            <>
              {/* Answer text — simple **bold** support */}
              <div className="text-theme-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                {stripInlineSources(message.content).split("\n").map((line, i) => {
                  const parts = line.split(/(\*\*[^*]+\*\*)/g);
                  return (
                    <p key={i} className={i > 0 ? "mt-2" : ""}>
                      {parts.map((part, j) =>
                        part.startsWith("**") && part.endsWith("**") ? (
                          <strong
                            key={j}
                            className="font-semibold text-gray-800 dark:text-white/90"
                          >
                            {part.slice(2, -2)}
                          </strong>
                        ) : (
                          part
                        ),
                      )}
                    </p>
                  );
                })}
              </div>

              {/* Source chips */}
              {message.sources && message.sources.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {message.sources.map((src) => (
                    <SourceChip
                      key={src.id}
                      filename={src.filename}
                      type={src.type}
                    />
                  ))}
                </div>
              )}

              {/* Feedback row (uncomment to enable) */}
              {/* <div className="mt-3 flex items-center gap-3 border-t border-gray-50 pt-3 dark:border-white/[0.03]">
                <button
                  onClick={() => onFeedback(message.id, "helpful")}
                  className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-theme-xs font-medium transition-colors ${
                    message.feedback === "helpful"
                      ? "bg-success-50 text-success-600 dark:bg-success-500/10 dark:text-success-400"
                      : "text-gray-500 hover:bg-gray-50 hover:text-gray-700 dark:hover:bg-white/[0.03] dark:hover:text-gray-300"
                  }`}
                >
                  👍 {tFeedback("helpful")}
                </button>

                <button
                  onClick={() => onFeedback(message.id, "not_helpful")}
                  className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-theme-xs font-medium transition-colors ${
                    message.feedback === "not_helpful"
                      ? "bg-error-50 text-error-500 dark:bg-error-500/10"
                      : "text-gray-500 hover:bg-gray-50 hover:text-gray-700 dark:hover:bg-white/[0.03] dark:hover:text-gray-300"
                  }`}
                >
                  👎 {tFeedback("notHelpful")}
                </button>

                <button
                  onClick={() => onRegenerate(message.id)}
                  className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-theme-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700 dark:hover:bg-white/[0.03] dark:hover:text-gray-300 transition-colors"
                >
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  {tFeedback("regenerate")}
                </button>
              </div> */}
            </>
          )}
        </div>
      </div>
    </div>
  );
}