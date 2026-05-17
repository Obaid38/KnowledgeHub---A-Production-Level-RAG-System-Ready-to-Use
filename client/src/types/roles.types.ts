// ── Permission actions ────────────────────────────────────────────────────────
export type PermissionAction = "view" | "create" | "edit" | "delete";

// ── A single permission cell state ───────────────────────────────────────────
export type PermissionState = boolean;

// ── One row in the matrix ─────────────────────────────────────────────────────
export interface PermissionRow {
  id:       string;
  category: string;
  view:     PermissionState;
  create:   PermissionState;
  edit:     PermissionState;
  delete:   PermissionState;
}

// ── A role's full permission set ──────────────────────────────────────────────
export interface RolePermissions {
  role:        SystemRole;
  label:       string;
  permissions: PermissionRow[];
}

// ── System roles ──────────────────────────────────────────────────────────────
export type SystemRole = "admin" | "manager" | "user" | "viewer" | string;

// ── Role definition returned from /rbac/roles ─────────────────────────────────
export interface RoleDefinition {
  role:            string;
  label:           string;
  isSystem:        boolean;
  createdAt:       string;
  permissionCount: number;  // total individual enabled actions across all rows
  userCount:       number;  // users currently assigned this role
}

// ── Metric card data ──────────────────────────────────────────────────────────
export interface RBACMetric {
  label:     string;
  value:     string | number;
  subtitle?: string;
}
