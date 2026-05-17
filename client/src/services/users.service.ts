// src/services/users.service.ts
import { privateAxios } from "@/lib/axios";
import { User, UserFilterTab } from "@/types/users";

// ─── Request / response types ─────────────────────────────────────────────────

export interface GetUsersParams {
  verified?: "Verified" | "Unverified";
  page?:     number;
  limit?:    number;
}

export interface GetUsersResponse {
  users:      User[];
  pagination: {
    total:      number;
    page:       number;
    limit:      number;
    totalPages: number;
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Build query params from a filter tab value. */
export function tabToParam(tab: UserFilterTab): GetUsersParams["verified"] | undefined {
  if (tab === "Verified")   return "Verified";
  if (tab === "Unverified") return "Unverified";
  return undefined;
}

// ─── Service functions ────────────────────────────────────────────────────────

/**
 * GET /users — paginated user list with optional verified filter.
 * Backend returns { users: [...], pagination: { total, page, limit, totalPages } }
 * The _id field is normalised to id by the backend's userPublic() helper.
 */
export async function apiGetUsers(params?: GetUsersParams): Promise<GetUsersResponse> {
  const { data } = await privateAxios.get<GetUsersResponse>("/users", { params });
  // Normalise _id → id (backend returns _id from Mongo)
  return {
    ...data,
    users: data.users.map((u: User & { _id?: string }) => ({
      ...u,
      id: u.id ?? u._id ?? "",
    })),
  };
}

/**
 * POST /users/:id/approve — verify a user account and assign a role.
 * The role must exist in the RBAC system before calling this.
 */
export async function apiApproveUser(id: string, role: string): Promise<void> {
  await privateAxios.post(`/users/${id}/approve`, { role });
}

/** POST /users/:id/reject — un-verify a user account. */
export async function apiRejectUser(id: string): Promise<void> {
  await privateAxios.post(`/users/${id}/reject`);
}

/** PATCH /users/:id/role — change a verified user's role. */
export async function apiUpdateUserRole(id: string, role: string): Promise<void> {
  await privateAxios.patch(`/users/${id}/role`, { role });
}

/** DELETE /users/:id — remove a user. Cannot delete own account. */
export async function apiDeleteUser(id: string): Promise<void> {
  await privateAxios.delete(`/users/${id}`);
}
