import { Document, DocumentCategory, DocumentStatus } from "@/types/documents";

export const CATEGORIES: DocumentCategory[]  = ["sop", "incident", "other", "compliance", "finance", "technical", "hr", "legal", "general", "cases"];
export const STATUSES: DocumentStatus[]      = ["Completed", "Processing", "Failed", "Pending"];
export const ACCEPTED_TYPES                  = ".pdf,.docx,.xlsx,.pptx,.jpg,.jpeg,.png";
export const ITEMS_PER_PAGE_OPTIONS          = [5, 10, 20, 50];
