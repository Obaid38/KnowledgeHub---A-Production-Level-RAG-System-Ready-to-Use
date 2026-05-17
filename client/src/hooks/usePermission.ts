"use client";

import { useAuthStore } from "@/store/authStore";
import type { PermissionAction } from "@/types/roles.types";
import { toast } from "react-toastify";
import { DEFAULT_ROLE_PERMISSIONS } from "@/constants/roles.constants";

// ── Maps frontend resource aliases to permission-matrix row IDs ───────────────
// Row IDs are aligned with the RBAC Design Documentation categories.
const RESOURCE_TO_ID: Record<string, string> = {
  // Canonical IDs (match the backend DEFAULT_ROWS)
  document:         "document",
  email:            "email",
  qa:               "qa",
  "knowledge-graph": "knowledge-graph",
  nlu:              "nlu",
  sap:              "sap",
  admin:            "admin",
  backup:           "backup",
  system:           "system",
  // Short aliases kept for backwards-compatibility with any existing can() calls
  doc:              "document",
  users:            "admin",
};

// ── Normalise the raw user role string to a known SystemRole ──────────────────
function toSystemRole(role: string | undefined): string | null {
  switch (role?.toLowerCase()) {
    case "superadmin": return "admin";
    case "admin":      return "admin";
    case "manager":    return "manager";
    case "user":       return "user";
    case "viewer":     return "viewer";
    default:           return null;
  }
}

export function usePermission() {
  const { user, permissions } = useAuthStore();

  console.log("usePermission - user:", permissions);

  const isSuperAdmin = user?.role?.toLowerCase() === "superadmin";
  const systemRole   = toSystemRole(user?.role);

  // Use the store-cached permissions (loaded on login/MFA/setUser).
  // Fall back to the bundled defaults if the store is empty (e.g. first paint
  // before the auth flow has completed a round-trip).
  const rows =
    permissions.length > 0
      ? permissions
      : DEFAULT_ROLE_PERMISSIONS.find((p) => p.role === systemRole)?.permissions ?? [];

  function can(action: PermissionAction, resource: string): boolean {
    if (!user) return false;
    if (isSuperAdmin) return true;

    const permId = RESOURCE_TO_ID[resource] ?? resource;
    const row    = rows.find((p) => p.id === permId);
    return row?.[action] === true;
  }

  function canAny(actions: PermissionAction[], resource: string): boolean {
    return actions.some((a) => can(a, resource));
  }

  function guard(
    action: PermissionAction,
    resource: string,
    message?: string,
  ): boolean {
    if (can(action, resource)) return true;

    toast.error(
      message ??
        `You don't have permission to ${action} ${resource.replace(/_/g, " ")}.`,
    );
    return false;
  }

  return { can, canAny, guard };
}
