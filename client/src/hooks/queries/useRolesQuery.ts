// src/hooks/queries/useRolesQuery.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  apiGetAllRoles,
  apiCreateRole,
  apiDeleteRole,
  apiGetRolePermissions,
  apiSaveRolePermissions,
  apiGetRBACMetrics,
  apiGetRoleStats,
} from "@/services/roles.service";
import { PermissionRow, SystemRole } from "@/types/roles.types";

export const RBAC_KEY = ["rbac"] as const;

// ── Role listing ──────────────────────────────────────────────────────────────

/** Fetch all roles (system + custom). */
export function useAllRolesQuery() {
  return useQuery({
    queryKey: [...RBAC_KEY, "roles"],
    queryFn:  apiGetAllRoles,
    staleTime: 60 * 1000,
  });
}

// ── Role CRUD ─────────────────────────────────────────────────────────────────

/** Create a new custom role — invalidates the roles list and metrics. */
export function useCreateRoleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ role, label }: { role: string; label: string }) =>
      apiCreateRole(role, label),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...RBAC_KEY, "roles"] });
      qc.invalidateQueries({ queryKey: [...RBAC_KEY, "metrics"] });
    },
  });
}

/** Delete a custom role — invalidates the roles list and metrics. */
export function useDeleteRoleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (role: string) => apiDeleteRole(role),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...RBAC_KEY, "roles"] });
      qc.invalidateQueries({ queryKey: [...RBAC_KEY, "metrics"] });
    },
  });
}

// ── Per-role stats ────────────────────────────────────────────────────────────

/** Fetch user count + enabled permission count for a role. */
export function useRoleStatsQuery(role: SystemRole) {
  return useQuery({
    queryKey: [...RBAC_KEY, "stats", role],
    queryFn:  () => apiGetRoleStats(role),
    staleTime: 30 * 1000,
    enabled:  !!role,
  });
}

// ── Permission matrix ─────────────────────────────────────────────────────────

/** Fetch the permission matrix for a specific role. */
export function useRolePermissionsQuery(role: SystemRole) {
  return useQuery({
    queryKey: [...RBAC_KEY, "permissions", role],
    queryFn:  () => apiGetRolePermissions(role),
    staleTime: 60 * 1000,
    enabled:  !!role,
  });
}

/** Fetch RBAC summary metrics (system roles, active users, etc.). */
export function useRBACMetricsQuery() {
  return useQuery({
    queryKey: [...RBAC_KEY, "metrics"],
    queryFn:  apiGetRBACMetrics,
    staleTime: 60 * 1000,
  });
}

/** Save the permission matrix for a role — invalidates that role's cache. */
export function useSaveRolePermissionsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ role, permissions }: { role: SystemRole; permissions: PermissionRow[] }) =>
      apiSaveRolePermissions(role, permissions),
    onSuccess: (_data, { role }) => {
      qc.invalidateQueries({ queryKey: [...RBAC_KEY, "permissions", role] });
      qc.invalidateQueries({ queryKey: [...RBAC_KEY, "roles"] });   // tab bar counts refresh
      qc.invalidateQueries({ queryKey: [...RBAC_KEY, "metrics"] });
    },
  });
}
