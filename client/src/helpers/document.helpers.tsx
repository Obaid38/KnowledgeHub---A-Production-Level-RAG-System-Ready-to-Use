import React from "react";
import { DocumentStatus } from "@/types/documents";

export function getTypeBadgeColor(
  type: string,
): "primary" | "success" | "warning" | "info" | "light" {
  const map: Record<string, "primary" | "success" | "warning" | "info" | "light"> = {
    PDF: "primary",
    Excel: "success",
    Word: "info",
    Email: "warning",
    Image: "light",
  };
  return map[type] ?? "light";
}

export function getStatusBadgeColor(
  status: DocumentStatus,
): "success" | "warning" | "error" | "info" {
  const map: Record<DocumentStatus, "success" | "warning" | "error" | "info"> = {
    Completed: "success",
    Processing: "warning",
    Failed: "error",
    Pending: "info",
  };
  return map[status];
}

export const Spinner = () => (
  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
  </svg>
);