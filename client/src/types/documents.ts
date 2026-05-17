export type DocumentCategory = "sop" | "incident" | "other" | "compliance" | "finance" | "technical" | "hr" | "legal" | "general" | "cases";
export type DocumentStatus   = "Completed" | "Processing" | "Failed" | "Pending";
export type DocumentSource   = "Upload" | "Email" | "SAP" | "API";

export interface Document {
  id: string;
  filename: string;
  type: string;
  size: string;
  sizeBytes: number;
  source: DocumentSource;
  status: DocumentStatus;
  category: DocumentCategory | null;
  uploadedAt: string;
}