// src/services/documents.service.ts
import { privateAxios } from "@/lib/axios";
import { Document, DocumentCategory, DocumentSource, DocumentStatus } from "@/types/documents";

// ─── Request / response types ─────────────────────────────────────────────────

export interface GetDocumentsParams {
  status?:   DocumentStatus;
  category?: DocumentCategory;
  source?:   DocumentSource;
  page?:     number;
  limit?:    number;
}

export interface GetDocumentsResponse {
  documents:  Document[];
  pagination: {
    total:      number;
    page:       number;
    limit:      number;
    totalPages: number;
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const MIME_TO_EXT: Record<string, string> = {
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPTX",
  "text/plain": "TXT",
  "image/png": "PNG",
  "image/jpeg": "JPG",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
    });
  } catch {
    return iso;
  }
}

/** Map a raw backend document object to the frontend Document type. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapDoc(raw: Record<string, any>): Document {
  return {
    id:         raw._id ?? raw.id ?? "",
    filename:   raw.filename ?? "",
    type:       MIME_TO_EXT[raw.mimetype] ?? raw.mimetype?.split("/").pop()?.toUpperCase() ?? "FILE",
    size:       formatBytes(raw.sizeBytes ?? raw.size ?? 0),
    sizeBytes:  raw.sizeBytes ?? raw.size ?? 0,
    source:     raw.source as DocumentSource ?? "Upload",
    status:     raw.status as DocumentStatus ?? "Pending",
    category:   raw.category as DocumentCategory ?? null,
    uploadedAt: raw.createdAt ? formatDate(raw.createdAt) : "—",
  };
}

// ─── Service functions ────────────────────────────────────────────────────────

/** GET /documents — paginated list of documents. */
export async function apiGetDocuments(params?: GetDocumentsParams): Promise<GetDocumentsResponse> {
  const { data } = await privateAxios.get<{ documents: Record<string, unknown>[]; pagination: GetDocumentsResponse["pagination"] }>("/documents", { params });
  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    documents:  (data.documents ?? []).map((d) => mapDoc(d as Record<string, any>)),
    pagination: data.pagination ?? { total: 0, page: 1, limit: 20, totalPages: 1 },
  };
}

/**
 * POST /documents/upload — upload one or more files (multipart/form-data).
 * Returns the created document records.
 */
export async function apiUploadDocuments(
  files: File[],
  category: DocumentCategory | null,
): Promise<Document[]> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  if (category) formData.append("category", category);

  // Setting Content-Type to null removes the instance-level "application/json"
  // default. Axios v1.x converts FormData → JSON when it sees "application/json",
  // so we clear it and let the browser's XHR set "multipart/form-data; boundary=…"
  // automatically when it detects a FormData body.
  const { data } = await privateAxios.post<{ documents: Record<string, unknown>[] }>(
    "/documents/upload",
    formData,
    { headers: { "Content-Type": null } },
  );
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (data.documents ?? []).map((d) => mapDoc(d as Record<string, any>));
}

/**
 * PATCH /documents/category — update a single document's category.
 * Wraps the bulk endpoint with a single-item array.
 */
export async function apiUpdateCategory(id: string, category: DocumentCategory): Promise<string> {
  const { data } = await privateAxios.patch<{ message: string }>(
    "/documents/category",
    { ids: [id], category }
  );
  return data?.message ?? "Category updated successfully.";
}

export async function apiBulkUpdateCategory(
  ids: string[],
  category: DocumentCategory,
): Promise<string> {
  const { data } = await privateAxios.patch<{ message: string }>(
    "/documents/category",
    { ids, category }
  );
  return data?.message ?? "Categories updated successfully.";
}

/** DELETE /documents — bulk-delete documents by ID. */
export async function apiDeleteDocuments(ids: string[]): Promise<string> {
  const { data } = await privateAxios.delete<{ message: string }>(
    "/documents",
    { data: { ids } }
  );
  return data.message ?? "Documents deleted successfully.";
}

/** POST /documents/process — trigger AI ingestion for selected documents. */
export async function apiProcessDocuments(documentIds: string[]): Promise<string> {
  const { data } = await privateAxios.post<{ data: { message: string } }>("/documents/process", { documentIds });
  return data.data?.message ?? "Processing started.";
}

export interface DocumentPreviewUrl {
  url:      string;
  expiresAt: string;
  filename:  string;
  mimetype:  string;
}

/** GET /documents/:id/preview — presigned URL for in-browser preview. */
export async function apiGetDocumentPreviewUrl(id: string): Promise<DocumentPreviewUrl> {
  const { data } = await privateAxios.get<DocumentPreviewUrl>(`/documents/${id}/preview`);
  return data;
}
