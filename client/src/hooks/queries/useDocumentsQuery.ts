// src/hooks/queries/useDocumentsQuery.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import {
  apiGetDocuments,
  apiUploadDocuments,
  apiUpdateCategory,
  apiBulkUpdateCategory,
  apiDeleteDocuments,
  apiProcessDocuments,
  GetDocumentsParams,
} from "@/services/documents.service";
import { DocumentCategory } from "@/types/documents";

function apiErrMsg(err: unknown): string {
  if (err && typeof err === "object" && "response" in err) {
    const res = (err as { response?: { data?: { error?: { message?: string } } } }).response;
    const msg = res?.data?.error?.message;
    if (msg) return msg;
  }
  return err instanceof Error ? err.message : "An unexpected error occurred.";
}

export const DOCS_KEY = ["documents"] as const;

/** Fetch documents with optional filters and pagination. */
export function useDocumentsQuery(params?: GetDocumentsParams) {
  return useQuery({
    queryKey: [...DOCS_KEY, params],
    queryFn:  () => apiGetDocuments(params),
    staleTime: 30 * 1000,
  });
}

/** Upload one or more files and add them to the documents list. */
export function useUploadDocumentsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ files, category }: { files: File[]; category: DocumentCategory | null }) =>
      apiUploadDocuments(files, category),
    onSuccess: () => {
      toast.success("Documents uploaded successfully.");
      qc.invalidateQueries({ queryKey: DOCS_KEY });
    },
    onError: (err) => toast.error(apiErrMsg(err)), // ← was missing
  });
}

/** Update a single document's category. */
export function useUpdateCategoryMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, category }: { id: string; category: DocumentCategory }) =>
      apiUpdateCategory(id, category),
    onSuccess: (message) => {
      toast.success(message);
      qc.invalidateQueries({ queryKey: DOCS_KEY });
    },
    onError: (err) => toast.error(apiErrMsg(err)),
  });
}

/** Bulk-update the category of multiple documents. */
export function useBulkUpdateCategoryMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ids, category }: { ids: string[]; category: DocumentCategory }) =>
      apiBulkUpdateCategory(ids, category),
    onSuccess: (message) => {
      toast.success(message);
      qc.invalidateQueries({ queryKey: DOCS_KEY });
    },
    onError: (err) => toast.error(apiErrMsg(err)),
  });
}

/** Bulk-delete documents by ID. */
export function useDeleteDocumentsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => apiDeleteDocuments(ids),
    onSuccess: (message) => {
      toast.success(message);
      qc.invalidateQueries({ queryKey: DOCS_KEY });
    },
    onError: (err) => toast.error(apiErrMsg(err)),
  });
}


/** Trigger AI ingestion for selected documents in sequential batches. */
export function useProcessDocumentsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (documentIds: string[]) => apiProcessDocuments(documentIds),
    onSuccess: (message) => {
      toast.success(message);
      qc.invalidateQueries({ queryKey: DOCS_KEY });
    },
    onError: (err) => toast.error(apiErrMsg(err)),
  });
}