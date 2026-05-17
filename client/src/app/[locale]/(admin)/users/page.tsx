"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { toast } from "react-toastify";
import { UserFilterTab } from "@/types/users";
import { User } from "@/types/users";
import {
  useUsersQuery,
  useApproveUserMutation,
  useRejectUserMutation,
  useUpdateUserRoleMutation,
  useDeleteUserMutation,
} from "@/hooks/queries/useUsersQuery";
import { tabToParam } from "@/services/users.service";
import { UserFilterTabs } from "@/components/user/users-management/UserFilterTabs";
import { UsersTable } from "@/components/user/users-management/UserTable";
import { AssignRoleModal } from "@/components/user/users-management/AssignRoleModal";
import { EditRoleModal } from "@/components/user/users-management/EditRoleModal";
import { DeleteConfirmModal } from "@/components/user/users-management/DeleteConfirmModal";
import Pagination from "@/components/tables/Pagination";

const PAGE_LIMIT = 10;

export default function UserManagement() {
  const t = useTranslations("users");

  const [activeTab,   setActiveTab]   = useState<UserFilterTab>("All");
  const [currentPage, setCurrentPage] = useState(1);
  const [limit,       setLimit]       = useState(PAGE_LIMIT);

  // ── Modal state ─────────────────────────────────────────────────────────────
  const [pendingApproveUser, setPendingApproveUser] = useState<User | null>(null);
  const [pendingEditUser,    setPendingEditUser]    = useState<User | null>(null);
  const [pendingDeleteUser,  setPendingDeleteUser]  = useState<User | null>(null);

  // ── Data fetching ───────────────────────────────────────────────────────────
  const params = {
    verified: tabToParam(activeTab),
    page:     currentPage,
    limit,
  };

  const { data, isLoading, isError } = useUsersQuery(params);

  const approveMutation    = useApproveUserMutation();
  const rejectMutation     = useRejectUserMutation();
  const editRoleMutation   = useUpdateUserRoleMutation();
  const deleteMutation     = useDeleteUserMutation();

  const actionLoading =
    approveMutation.isPending  ? (approveMutation.variables  as { id: string }).id :
    rejectMutation.isPending   ? rejectMutation.variables    as string :
    editRoleMutation.isPending ? (editRoleMutation.variables as { id: string }).id :
    deleteMutation.isPending   ? deleteMutation.variables    as string :
    null;

  const counts = useMemo<Record<UserFilterTab, number>>(() => ({
    All:        activeTab === "All"        ? (data?.pagination.total ?? 0) : 0,
    Verified:   activeTab === "Verified"   ? (data?.pagination.total ?? 0) : 0,
    Unverified: activeTab === "Unverified" ? (data?.pagination.total ?? 0) : 0,
  }), [data, activeTab]);

  const totalPages = data?.pagination.totalPages ?? 1;
  const users      = data?.users ?? [];

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleApproveClick = (user: User) => setPendingApproveUser(user);

  const handleApproveConfirm = (userId: string, role: string) => {
    approveMutation.mutate(
      { id: userId, role },
      {
        onSuccess: () => {
          toast.success(`User approved and assigned role "${role}" successfully.`);
          setPendingApproveUser(null);
        },
        onError: (err) => toast.error(err.message),
      },
    );
  };

  const handleReject = (id: string) => {
    rejectMutation.mutate(id, {
      onError: (err) => toast.error(err.message),
    });
  };

  const handleEditRoleClick = (user: User) => setPendingEditUser(user);

  const handleEditRoleConfirm = (userId: string, role: string) => {
    editRoleMutation.mutate(
      { id: userId, role },
      {
        onSuccess: () => {
          toast.success(`User role updated to "${role}" successfully.`);
          setPendingEditUser(null);
        },
        onError: (err) => toast.error(err.message),
      },
    );
  };

  const handleDeleteClick = (user: User) => setPendingDeleteUser(user);

  const handleDeleteConfirm = (userId: string) => {
    deleteMutation.mutate(userId, {
      onSuccess: () => {
        toast.success("User deleted successfully.");
        setPendingDeleteUser(null);
      },
      onError: (err) => toast.error(err.message),
    });
  };

  const handleTabChange = (tab: UserFilterTab) => {
    setActiveTab(tab);
    setCurrentPage(1);
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  if (isError) {
    return (
      <div className="space-y-6">
        <div><h1>{t("title")}</h1></div>
        <p className="text-error-500">Failed to load users. Please try again.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1>{t("title")}</h1>
        <p>{t("subtitle")}</p>
      </div>

      <UserFilterTabs
        active={activeTab}
        counts={counts}
        onChange={handleTabChange}
      />

      <UsersTable
        users={isLoading ? [] : users}
        activeTab={activeTab}
        onApprove={handleApproveClick}
        onReject={handleReject}
        onEditRole={handleEditRoleClick}
        onDelete={handleDeleteClick}
        actionLoading={actionLoading}
      />

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/5 dark:bg-white/3">
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          total={data?.pagination.total ?? 0}
          limit={limit}
          onPageChange={setCurrentPage}
          onLimitChange={(l) => { setLimit(l); setCurrentPage(1); }}
        />
      </div>

      {/* ── Approve Modal ── */}
      <AssignRoleModal
        isOpen={pendingApproveUser !== null}
        user={pendingApproveUser}
        onClose={() => setPendingApproveUser(null)}
        onConfirm={handleApproveConfirm}
        isLoading={approveMutation.isPending}
      />

      {/* ── Edit Role Modal ── */}
      <EditRoleModal
        isOpen={pendingEditUser !== null}
        user={pendingEditUser}
        onClose={() => setPendingEditUser(null)}
        onConfirm={handleEditRoleConfirm}
        isLoading={editRoleMutation.isPending}
      />

      {/* ── Delete Confirm Modal ── */}
      <DeleteConfirmModal
        isOpen={pendingDeleteUser !== null}
        user={pendingDeleteUser}
        onClose={() => setPendingDeleteUser(null)}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}
