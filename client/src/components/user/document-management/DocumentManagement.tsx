"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import Badge from "@/components/ui/badge/Badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Document, DocumentCategory, DocumentStatus } from "@/types/documents";
import { STATUSES } from "@/constants/document.contants";
import {
  useDocumentsQuery,
  useUploadDocumentsMutation,
  useUpdateCategoryMutation,
  useBulkUpdateCategoryMutation,
  useDeleteDocumentsMutation,
  useProcessDocumentsMutation,
} from "@/hooks/queries/useDocumentsQuery";
import { getTypeBadgeColor, getStatusBadgeColor } from "@/helpers/document.helpers";
import { UploadZone } from "./UploadZone";
import { InlineCategoryEditor } from "./InlineCategory";
import { BulkCategoryToolbar } from "./BulkCategoryToolbar";
import { Can } from "@/components/auth/Can";
import Pagination from "@/components/tables/Pagination";
import { UploadModal } from "./UploadModal";
import { DeleteModal } from "./DeleteModal";
import { DocumentPreviewModal } from "./DocumentPreviewModal";
import { useDocumentSocket } from "@/hooks/useDocumentSocket";


export default function DocumentManagement() {
  const t    = useTranslations("documents");
  const tTbl = useTranslations("documents.table");

  const [selectedIds,        setSelectedIds]        = useState<Set<string>>(new Set());
  const [search,             setSearch]             = useState("");
  const [statusFilter,       setStatusFilter]       = useState<DocumentStatus | "All">("All");
  const [currentPage,        setCurrentPage]        = useState(1);
  const [limit,              setLimit]              = useState(10);
  const [showDeleteModal,    setShowDeleteModal]    = useState(false);
  const [pendingFiles,       setPendingFiles]       = useState<File[] | null>(null);
  const [previewDoc,         setPreviewDoc]         = useState<Document | null>(null);
  // IDs submitted for processing but not yet confirmed by the socket —
  // prevents re-submission during the gap between click and status update.
  const [localProcessingIds, setLocalProcessingIds] = useState<Set<string>>(new Set());

  // Real-time status updates via WebSocket.
  // When a document finishes (Completed/Failed), remove it from the local tracking set.
  useDocumentSocket((id) =>
    setLocalProcessingIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    }),
  );

  // ── Data fetching ────────────────────────────────────────────────────────────
  const queryParams = {
    status:   statusFilter !== "All" ? statusFilter : undefined,
    page:     currentPage,
    limit,
  };

  const { data, isLoading } = useDocumentsQuery(queryParams);

  const uploadMutation          = useUploadDocumentsMutation();
  const updateCategoryMutation  = useUpdateCategoryMutation();
  const bulkCategoryMutation    = useBulkUpdateCategoryMutation();
  const deleteMutation          = useDeleteDocumentsMutation();
  const processMutation         = useProcessDocumentsMutation();

  // ── Derived values ───────────────────────────────────────────────────────────
  // Client-side search filter on the current page
  const documents  = data?.documents ?? [];
  const filtered   = documents.filter((d) =>
    d.filename.toLowerCase().includes(search.toLowerCase()),
  );
  const totalPages = data?.pagination.totalPages ?? 1;
  const total      = data?.pagination.total ?? 0;

  const allOnPageSelected  = filtered.length > 0 && filtered.every((d) => selectedIds.has(d.id));
  const someOnPageSelected = filtered.some((d) => selectedIds.has(d.id));

  // True when at least one selected document is already being processed
  // (either confirmed by the server status, or locally tracked since the last click)
  const anySelectedProcessing = filtered.some(
    (d) => selectedIds.has(d.id) && (d.status === "Processing" || localProcessingIds.has(d.id)),
  );

  // ── Selection helpers ────────────────────────────────────────────────────────
  const toggleSelectAll = () => {
    if (allOnPageSelected) {
      setSelectedIds((prev) => {
        const n = new Set(prev);
        filtered.forEach((d) => n.delete(d.id));
        return n;
      });
    } else {
      setSelectedIds((prev) => {
        const n = new Set(prev);
        filtered.forEach((d) => n.add(d.id));
        return n;
      });
    }
  };

  const toggleSelectOne = (id: string) =>
    setSelectedIds((prev) => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  // ── Action handlers ───────────────────────────────────────────────────────────
  const handleUploadConfirm = async (category: DocumentCategory | null) => {
    if (!pendingFiles) return;
    uploadMutation.mutate(
      { files: pendingFiles, category },
      { onSettled: () => setPendingFiles(null) },
    );
  };

  const handleCategoryUpdate = async (id: string, category: DocumentCategory) => {
    updateCategoryMutation.mutate({ id, category });
  };

  const handleBulkCategoryUpdate = async (category: DocumentCategory) => {
    const ids = Array.from(selectedIds);
    bulkCategoryMutation.mutate(
      { ids, category },
      { onSuccess: () => setSelectedIds(new Set()) },
    );
  };

  const handleProcess = () => {
    const ids = Array.from(selectedIds);
    // Mark IDs as processing immediately so the button is disabled before
    // the server or socket has a chance to update the status.
    setLocalProcessingIds((prev) => new Set([...prev, ...ids]));
    processMutation.mutate(ids, {
      onError: () => {
        // API rejected the request — clear the local lock so the user can retry.
        setLocalProcessingIds((prev) => {
          const next = new Set(prev);
          ids.forEach((id) => next.delete(id));
          return next;
        });
      },
    });
  };

  const handleDeleteConfirm = async () => {
    deleteMutation.mutate(Array.from(selectedIds), {
      onSuccess: () => {
        setSelectedIds(new Set());
        setShowDeleteModal(false);
      },
    });
  };

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <div>
        <h1>{t("title")}</h1>
        <p>{t("subtitle")}</p>
      </div>

      <Can action="create" resource="document">
        <UploadZone
          onFilesSelected={setPendingFiles}
          uploading={uploadMutation.isPending}
        />
      </Can>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/[0.05] dark:bg-white/[0.03]">

        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-5 py-4 dark:border-white/[0.05]">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-base">{tTbl("allDocuments")}</h2>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-theme-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                {total}
              </span>
            </div>

            {selectedIds.size > 0 && (
              <Can action={["edit", "delete"]} resource="document">
                <BulkCategoryToolbar
                  selectedCount={selectedIds.size}
                  onUpdateCategory={handleBulkCategoryUpdate}
                  onDelete={() => setShowDeleteModal(true)}
                />
              </Can>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={tTbl("searchPlaceholder")}
                className="h-10 w-56 rounded-lg border border-gray-200 bg-white pl-9 pr-3 text-theme-sm text-gray-700 placeholder-gray-400 shadow-theme-xs focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:placeholder-gray-500"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value as DocumentStatus | "All"); setCurrentPage(1); }}
              className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-theme-sm text-gray-700 shadow-theme-xs focus:border-brand-500 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
            >
              <option value="All">{tTbl("allStatus")}</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            <Can action="create" resource="document">
              <div
                title={anySelectedProcessing ? "One or more selected documents are already being processed" : undefined}
                className="inline-flex"
              >
                <button
                  onClick={handleProcess}
                  disabled={selectedIds.size === 0 || processMutation.isPending || anySelectedProcessing}
                  className="h-10 rounded-lg bg-brand-500 px-4 text-theme-sm font-medium text-white shadow-theme-xs transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {processMutation.isPending ? "Processing…" : "Process"}
                </button>
              </div>
            </Can>
          </div>
        </div>

        {/* Table */}
        <div className="max-w-full overflow-x-auto">
          <div className="min-w-[960px]">
            <Table>
              <TableHeader className="border-b border-gray-100 dark:border-white/[0.05]">
                <TableRow>
                  <TableCell isHeader className="w-10 px-5 py-3">
                    <Can action={["edit", "delete"]} resource="document">
                      <input
                        type="checkbox"
                        checked={allOnPageSelected}
                        ref={(el) => {
                          if (el) el.indeterminate = someOnPageSelected && !allOnPageSelected;
                        }}
                        onChange={toggleSelectAll}
                        className="h-4 w-4 cursor-pointer rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-600"
                      />
                    </Can>
                  </TableCell>
                  {(["filename", "type", "size", "source", "category", "status", "uploaded", "actions"] as const).map((col) => (
                    <TableCell key={col} isHeader className="text-start px-5 py-3 text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                      {tTbl(`columns.${col}`)}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHeader>

              <TableBody className="divide-y divide-gray-100 dark:divide-white/[0.05]">
                {isLoading ? (
                  <TableRow>
                    <TableCell className="col-span-9 px-5 py-16 text-center text-theme-sm text-gray-400 dark:text-gray-500">
                      Loading…
                    </TableCell>
                  </TableRow>
                ) : filtered.length === 0 ? (
                  <TableRow>
                    <TableCell className="col-span-9 px-5 py-16 text-center text-theme-sm text-gray-400 dark:text-gray-500">
                      {tTbl("noDocuments")}
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((doc: Document) => (
                    <TableRow
                      key={doc.id}
                      className={`transition-colors ${
                        selectedIds.has(doc.id)
                          ? "bg-brand-50/50 dark:bg-brand-500/5"
                          : "hover:bg-gray-50/50 dark:hover:bg-white/[0.02]"
                      }`}
                    >
                      <TableCell className="px-5 py-4 text-start">
                        <Can action={["edit", "delete"]} resource="document">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(doc.id)}
                            onChange={() => toggleSelectOne(doc.id)}
                            className="h-4 w-4 cursor-pointer rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-600"
                          />
                        </Can>
                      </TableCell>

                      <TableCell className="px-4 py-4 text-start">
                        <span className="text-theme-sm font-medium text-gray-800 dark:text-white/90">
                          {doc.filename}
                        </span>
                      </TableCell>

                      <TableCell className="px-4 py-4">
                        <Badge size="sm" color={getTypeBadgeColor(doc.type)}>{doc.type}</Badge>
                      </TableCell>

                      <TableCell className="px-4 py-4 text-theme-sm text-gray-500 dark:text-gray-400">
                        {doc.size}
                      </TableCell>

                      <TableCell className="px-4 py-4">
                        <Badge size="sm" variant="light" color="light">{doc.source}</Badge>
                      </TableCell>

                      <TableCell className="px-4 py-4">
                        <Can
                          action="edit"
                          resource="document"
                          fallback={
                            <span className="text-theme-sm text-gray-500 dark:text-gray-400">
                              {doc.category ?? "—"}
                            </span>
                          }
                        >
                          <InlineCategoryEditor
                            docId={doc.id}
                            current={doc.category}
                            onSave={handleCategoryUpdate}
                          />
                        </Can>
                      </TableCell>

                      <TableCell className="px-4 py-4">
                        <Badge size="sm" color={getStatusBadgeColor(doc.status)}>
                          {doc.status}
                        </Badge>
                      </TableCell>

                      <TableCell className="px-4 py-4 text-theme-sm text-gray-500 dark:text-gray-400">
                        {doc.uploadedAt}
                      </TableCell>

                      <TableCell className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <Can action="view" resource="document">
                            <button
                              onClick={() => setPreviewDoc(doc)}
                              className="text-theme-sm font-medium text-brand-500 hover:text-brand-600 hover:underline"
                            >
                              {tTbl("preview")}
                            </button>
                          </Can>
                          <Can action="delete" resource="document">
                            <button
                              onClick={() => {
                                setSelectedIds(new Set([doc.id]));
                                setShowDeleteModal(true);
                              }}
                              className="text-theme-sm font-medium text-error-500 hover:text-error-600 hover:underline"
                            >
                              {tTbl("delete")}
                            </button>
                          </Can>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>

        {/* Pagination */}
        <div className="border-t border-gray-100 dark:border-white/[0.05]">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            total={total}
            limit={limit}
            onPageChange={setCurrentPage}
            onLimitChange={(l) => { setLimit(l); setCurrentPage(1); }}
          />
        </div>
      </div>

      {pendingFiles && (
        <UploadModal
          files={pendingFiles}
          onConfirm={handleUploadConfirm}
          onCancel={() => setPendingFiles(null)}
          uploading={uploadMutation.isPending}
        />
      )}

      {showDeleteModal && (
        <DeleteModal
          count={selectedIds.size}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setShowDeleteModal(false)}
          loading={deleteMutation.isPending}
        />
      )}

      <DocumentPreviewModal
        doc={previewDoc}
        onClose={() => setPreviewDoc(null)}
      />
    </div>
  );
}
