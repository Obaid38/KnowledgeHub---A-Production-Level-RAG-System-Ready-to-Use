// src/services/roles.service.ts
import { privateAxios } from "@/lib/axios";
import { PermissionRow, RoleDefinition, SystemRole } from "@/types/roles.types";

export interface RBACMetrics {
  systemRoles:        number;
  permissionsDefined: number;
  activeUsers:        number;
  customRoles:        number;
}

// ── Role management ───────────────────────────────────────────────────────────

/**
 * GET /rbac/roles
 * Returns all roles (system + custom) with metadata.
 */
export async function apiGetAllRoles(): Promise<RoleDefinition[]> {
  const { data } = await privateAxios.get<{ roles: RoleDefinition[] }>("/rbac/roles");
  return data.roles ?? [];
}

/**
 * POST /rbac/roles
 * Create a new custom role. Returns the created role.
 */
export async function apiCreateRole(role: string, label: string): Promise<RoleDefinition> {
  const { data } = await privateAxios.post<{ role: RoleDefinition }>("/rbac/roles", { role, label });
  return data.role;
}

/**
 * DELETE /rbac/roles/:role
 * Delete a custom role. System roles cannot be deleted.
 */
export async function apiDeleteRole(role: string): Promise<void> {
  await privateAxios.delete(`/rbac/roles/${role}`);
}

// ── Permission matrix ─────────────────────────────────────────────────────────

/**
 * GET /rbac/roles/:role/permissions
 * Returns the permission matrix for the given role.
 * Auto-seeds with default permissions if the role has never been configured.
 */
export async function apiGetRolePermissions(role: SystemRole): Promise<PermissionRow[]> {
  const { data } = await privateAxios.get<{ role: string; permissions: PermissionRow[] }>(
    `/rbac/roles/${role}/permissions`,
  );
  return data.permissions ?? [];
}

/**
 * PUT /rbac/roles/:role/permissions
 * Persist the entire permission matrix for a role.
 */
export async function apiSaveRolePermissions(
  role: SystemRole,
  permissions: PermissionRow[],
): Promise<void> {
  await privateAxios.put(`/rbac/roles/${role}/permissions`, { permissions });
}

// ── Per-role stats ────────────────────────────────────────────────────────────

export interface RoleStats {
  userCount:        number;
  permissionCount:  number;
}

/** GET /rbac/roles/:role/stats — user count + enabled permission count for a role. */
export async function apiGetRoleStats(role: string): Promise<RoleStats> {
  const { data } = await privateAxios.get<RoleStats>(`/rbac/roles/${role}/stats`);
  return data;
}

// ── Metrics ───────────────────────────────────────────────────────────────────

/** GET /rbac/metrics — summary counts for the RBAC metric cards. */
export async function apiGetRBACMetrics(): Promise<RBACMetrics> {
  const { data } = await privateAxios.get<RBACMetrics>("/rbac/metrics");
  return data;
}
