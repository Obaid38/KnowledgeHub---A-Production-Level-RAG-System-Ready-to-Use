"use client";

import React, { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { toast } from "react-toastify";
import { Plus, Trash2 } from "lucide-react";
import { SystemRole, PermissionRow, PermissionAction } from "@/types/roles.types";
import {
  useAllRolesQuery,
  useCreateRoleMutation,
  useDeleteRoleMutation,
  useRolePermissionsQuery,
  useSaveRolePermissionsMutation,
} from "@/hooks/queries/useRolesQuery";
import { RBACMetricCards } from "./RolesMetricCards";
import { RoleTabBar } from "./RoleTabBar";
import { PermissionMatrix } from "./PermissionMatrix";
import { CreateRoleModal } from "./CreateRoleModal";

function getToastTheme(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export default function RoleBasedAccessControl() {
  const t      = useTranslations("rbac");
  const tToast = useTranslations("rbac.toast");

  const [activeRole,       setActiveRole]       = useState<SystemRole>("admin");
  const [draftMap,         setDraftMap]         = useState<Partial<Record<SystemRole, PermissionRow[]>>>({});
  const [showCreateModal,  setShowCreateModal]  = useState(false);
  const [deleteConfirmRole, setDeleteConfirmRole] = useState<string | null>(null);

  // ── API hooks ─────────────────────────────────────────────────────────────
  const { data: allRoles = [], isLoading: rolesLoading } = useAllRolesQuery();
  const { data: serverRows, isLoading: permissionsLoading } = useRolePermissionsQuery(activeRole);

  const saveMutation   = useSaveRolePermissionsMutation();
  const createMutation = useCreateRoleMutation();
  const deleteMutation = useDeleteRoleMutation();

  const baseRows: PermissionRow[] = serverRows ?? [];

  // The editable draft: use the in-memory draft if the user has made changes,
  // otherwise fall back to server rows
  const currentRows = draftMap[activeRole] ?? baseRows;
  const isDirty     = JSON.stringify(currentRows) !== JSON.stringify(baseRows);

  const activeRoleDef = allRoles.find((r) => r.role === activeRole);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleTabChange = (role: SystemRole) => {
    setActiveRole(role);
    setDeleteConfirmRole(null);
  };

  const handleToggle = useCallback(
    (rowId: string, action: PermissionAction) => {
      setDraftMap((prev) => {
        const base = prev[activeRole] ?? baseRows;
        const rows = base.map((row) =>
          row.id === rowId ? { ...row, [action]: !row[action] } : row,
        );
        return { ...prev, [activeRole]: rows };
      });
    },
    [activeRole, baseRows],
  );

  /** Toggle all actions for a single category row. */
  const handleToggleRow = useCallback(
    (rowId: string, value: boolean) => {
      setDraftMap((prev) => {
        const base = prev[activeRole] ?? baseRows;
        const rows = base.map((row) =>
          row.id === rowId
            ? { ...row, view: value, create: value, edit: value, delete: value }
            : row,
        );
        return { ...prev, [activeRole]: rows };
      });
    },
    [activeRole, baseRows],
  );

  /** Select or clear every permission cell across all rows. */
  const handleSelectAll = useCallback(
    (value: boolean) => {
      setDraftMap((prev) => {
        const base = prev[activeRole] ?? baseRows;
        const rows = base.map((row) => ({
          ...row,
          view: value, create: value, edit: value, delete: value,
        }));
        return { ...prev, [activeRole]: rows };
      });
    },
    [activeRole, baseRows],
  );

  const handleSave = () => {
    const theme = getToastTheme();
    saveMutation.mutate(
      { role: activeRole, permissions: currentRows },
      {
        onSuccess: () => {
          setDraftMap((prev) => { const n = { ...prev }; delete n[activeRole]; return n; });
          toast.success(tToast("saveSuccess"), {
            theme, position: "top-center", autoClose: 2500,
            hideProgressBar: false, closeOnClick: true, pauseOnHover: true, draggable: true,
          });
        },
        onError: (err) => {
          toast.error(tToast("saveError"), {
            theme, position: "top-center", autoClose: 4000,
            hideProgressBar: false, closeOnClick: true, pauseOnHover: true, draggable: true,
          });
        },
      },
    );
  };

  const handleDiscard = () => {
    setDraftMap((prev) => { const n = { ...prev }; delete n[activeRole]; return n; });
    toast.info(tToast("discarded"), {
      theme: getToastTheme(), position: "top-center", autoClose: 2000,
    });
  };

  const handleCreateRole = (role: string, label: string) => {
    createMutation.mutate(
      { role, label },
      {
        onSuccess: (newRole) => {
          toast.success(`Role "${label}" created successfully.`, {
            theme: getToastTheme(), position: "top-center", autoClose: 2500,
          });
          setShowCreateModal(false);
          setActiveRole(newRole.role);
        },
        onError: (err) => {
          toast.error(err.message || "Failed to create role.", {
            theme: getToastTheme(), position: "top-center", autoClose: 4000,
          });
        },
      },
    );
  };

  const handleDeleteRole = (roleKey: string) => {
    if (deleteConfirmRole !== roleKey) {
      // First click: ask for confirmation
      setDeleteConfirmRole(roleKey);
      return;
    }
    // Second click: confirmed — delete
    deleteMutation.mutate(roleKey, {
      onSuccess: () => {
        toast.success(`Role deleted successfully.`, {
          theme: getToastTheme(), position: "top-center", autoClose: 2500,
        });
        setDeleteConfirmRole(null);
        // Switch back to admin if the active role was deleted
        if (activeRole === roleKey) setActiveRole("admin");
      },
      onError: (err) => {
        toast.error(err.message || "Failed to delete role.", {
          theme: getToastTheme(), position: "top-center", autoClose: 4000,
        });
        setDeleteConfirmRole(null);
      },
    });
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <div>
        <h1>{t("title")}</h1>
        <p>{t("subtitle")}</p>
      </div>

      <RBACMetricCards />

      {/* ── Role Tab Bar + Create button ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {rolesLoading ? (
          <div className="flex gap-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-9 w-28 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800" />
            ))}
          </div>
        ) : (
          <RoleTabBar
            active={activeRole}
            roles={allRoles}
            onChange={handleTabChange}
          />
        )}

        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-1.5 rounded-lg bg-brand-500 px-4 py-2 text-theme-sm font-medium text-white transition-colors hover:bg-brand-600"
        >
          <Plus className="h-4 w-4" />
          New Role
        </button>
      </div>

      {/* ── Delete button for custom roles ── */}
      {activeRoleDef && !activeRoleDef.isSystem && (
        <div className="flex items-center gap-3 rounded-lg border border-error-100 bg-error-50 px-4 py-3 dark:border-error-900/30 dark:bg-error-900/10">
          <p className="flex-1 text-theme-sm text-error-700 dark:text-error-400">
            This is a custom role. Deleting it cannot be undone.
          </p>
          <button
            onClick={() => handleDeleteRole(activeRole)}
            disabled={deleteMutation.isPending}
            className="flex items-center gap-1.5 rounded-lg border border-error-300 bg-white px-3 py-1.5 text-theme-xs font-semibold text-error-600 transition-colors hover:bg-error-50 disabled:opacity-50 dark:border-error-800 dark:bg-transparent dark:text-error-400 dark:hover:bg-error-900/20"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {deleteMutation.isPending
              ? "Deleting…"
              : deleteConfirmRole === activeRole
              ? "Confirm Delete"
              : "Delete Role"}
          </button>
          {deleteConfirmRole === activeRole && (
            <button
              onClick={() => setDeleteConfirmRole(null)}
              className="text-theme-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              Cancel
            </button>
          )}
        </div>
      )}

      <PermissionMatrix
        rows={currentRows}
        isLoading={permissionsLoading}
        isDirty={isDirty}
        saving={saveMutation.isPending}
        onToggle={handleToggle}
        onToggleRow={handleToggleRow}
        onSelectAll={handleSelectAll}
        onSave={handleSave}
        onDiscard={handleDiscard}
      />

      <CreateRoleModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onConfirm={handleCreateRole}
        isLoading={createMutation.isPending}
      />
    </div>
  );
}
