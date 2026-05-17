"use client";

import React, { useEffect, useState } from "react";
import Modal from "@/components/ui/modal";
import { apiGetDocumentPreviewUrl } from "@/services/documents.service";
import type { Document } from "@/types/documents";
import { Download } from "lucide-react";

interface DocumentPreviewModalProps {
  doc:     Document | null;
  onClose: () => void;
}

type PreviewState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; url: string; mimetype: string; filename: string }
  | { status: "error"; message: string };

// ─── Renderers per MIME type ──────────────────────────────────────────────────

function PdfPreview({ url }: { url: string }) {
  return (
    <iframe
      src={url}
      title="Document preview"
      className="h-full w-full rounded-lg border-0"
    />
  );
}

function TextPreview({ url, filename }: { url: string; filename: string }) {
  const [content, setContent] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState(false);

  useEffect(() => {
    fetch(url)
      .then((r) => r.text())
      .then(setContent)
      .catch(() => setFetchError(true));
  }, [url]);

  if (fetchError) {
    return (
      <UnsupportedPreview url={url} filename={filename} reason="Could not load text content." />
    );
  }

  if (content === null) {
    return (
      <div className="flex h-full items-center justify-center">
        <span className="text-theme-sm text-gray-400">Loading content…</span>
      </div>
    );
  }

  return (
    <pre className="h-full overflow-auto rounded-lg bg-gray-50 p-4 text-theme-sm text-gray-700 dark:bg-gray-800 dark:text-gray-300 whitespace-pre-wrap break-words">
      {content}
    </pre>
  );
}

function UnsupportedPreview({
  url,
  filename,
  reason,
}: {
  url: string;
  filename: string;
  reason?: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gray-100 dark:bg-gray-800">
        <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <div>
        <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-300">
          Preview not available for this file type
        </p>
        {reason && (
          <p className="mt-1 text-theme-xs text-gray-400">{reason}</p>
        )}
      </div>
      <a
        href={url}
        download={filename}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-theme-sm font-medium text-white shadow-theme-xs transition-colors hover:bg-brand-600"
      >
        <Download className="h-4 w-4" strokeWidth={2} />
        Download file
      </a>
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function DocumentPreviewModal({ doc, onClose }: DocumentPreviewModalProps) {
  const [state, setState] = useState<PreviewState>({ status: "idle" });

  useEffect(() => {
    if (!doc) {
      setState({ status: "idle" });
      return;
    }

    setState({ status: "loading" });

    apiGetDocumentPreviewUrl(doc.id)
      .then(({ url, mimetype, filename }) => {
        setState({ status: "ready", url, mimetype, filename });
      })
      .catch(() => {
        setState({ status: "error", message: "Failed to load document preview." });
      });
  }, [doc]);

  function renderContent() {
    if (state.status === "loading") {
      return (
        <div className="flex h-full items-center justify-center">
          <span className="text-theme-sm text-gray-400">Loading preview…</span>
        </div>
      );
    }

    if (state.status === "error") {
      return (
        <div className="flex h-full items-center justify-center">
          <span className="text-theme-sm text-error-500">{state.message}</span>
        </div>
      );
    }

    if (state.status === "ready") {
      const { url, mimetype, filename } = state;

      if (mimetype === "application/pdf") {
        return <PdfPreview url={url} />;
      }
      if (mimetype === "text/plain") {
        return <TextPreview url={url} filename={filename} />;
      }
      // DOCX, XLSX and other types cannot be rendered inline
      return <UnsupportedPreview url={url} filename={filename} />;
    }

    return null;
  }

  return (
    <Modal
      isOpen={!!doc}
      onClose={onClose}
      maxWidth="max-w-4xl"
      showCloseButton
      closeOnBackdrop
    >
      {/* Header */}
      <div className="mb-4 pr-8">
        <h2 className="truncate text-base font-semibold text-gray-800 dark:text-white/90">
          {doc?.filename ?? "Document Preview"}
        </h2>
        <p className="mt-0.5 text-theme-xs text-gray-400">
          {doc?.type} · {doc?.size}
        </p>
      </div>

      {/* Preview area */}
      <div className="h-[65vh]">{renderContent()}</div>
    </Modal>
  );
}
