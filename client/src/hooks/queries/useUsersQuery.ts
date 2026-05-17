// src/hooks/queries/useUsersQuery.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  apiGetUsers,
  apiApproveUser,
  apiRejectUser,
  apiUpdateUserRole,
  apiDeleteUser,
  GetUsersParams,
} from "@/services/users.service";

export const USERS_KEY = ["users"] as const;

/**
 * Fetch a paginated, optionally filtered list of users.
 * The query key includes all params so React Query caches each
 * filter/page combination separately.
 */
export function useUsersQuery(params?: GetUsersParams) {
  return useQuery({
    queryKey: [...USERS_KEY, params],
    queryFn:  () => apiGetUsers(params),
    staleTime: 30 * 1000, // 30 s
  });
}

/** Approve a user with a role — invalidates the users list and role stats. */
export function useApproveUserMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => apiApproveUser(id, role),
    onSuccess: (_data, { role }) => {
      qc.invalidateQueries({ queryKey: USERS_KEY });
      // Invalidate stats for the assigned role so the "Users" count card refreshes
      qc.invalidateQueries({ queryKey: ["rbac", "stats", role] });
    },
  });
}

/** Reject (un-verify) a user. */
export function useRejectUserMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: apiRejectUser,
    onSuccess:  () => qc.invalidateQueries({ queryKey: USERS_KEY }),
  });
}

/** Update the role of an existing user. */
export function useUpdateUserRoleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => apiUpdateUserRole(id, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: USERS_KEY }),
  });
}

/** Permanently delete a user. */
export function useDeleteUserMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: apiDeleteUser,
    onSuccess:  () => qc.invalidateQueries({ queryKey: USERS_KEY }),
  });
}
