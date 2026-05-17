"use client";

import React, { useState, useEffect } from "react";
import Modal from "@/components/ui/modal";
import { useAllRolesQuery } from "@/hooks/queries/useRolesQuery";
import { User } from "@/types/users";

interface EditRoleModalProps {
  isOpen:    boolean;
  user:      User | null;
  onClose:   () => void;
  onConfirm: (userId: string, role: string) => void;
  isLoading: boolean;
}

export function EditRoleModal({
  isOpen,
  user,
  onClose,
  onConfirm,
  isLoading,
}: EditRoleModalProps) {
  const [selectedRole, setSelectedRole] = useState<string>("");

  const { data: roles = [], isLoading: rolesLoading } = useAllRolesQuery();

  // Pre-select the user's current role (lowercase key) when the modal opens
  useEffect(() => {
    if (user) {
      setSelectedRole(user.role.toLowerCase());
    }
  }, [user]);

  const handleConfirm = () => {
    if (!user || !selectedRole) return;
    onConfirm(user.id, selectedRole);
  };

  const handleClose = () => {
    setSelectedRole("");
    onClose();
  };

  const fullName = user ? `${user.firstName} ${user.lastName}` : "";

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      maxWidth="max-w-md"
      showCloseButton
    >
      {/* ── Header ── */}
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          Edit User Role
        </h2>
        <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
          Change the role for{" "}
          <span className="font-medium text-gray-700 dark:text-white/80">{fullName}</span>.
        </p>
      </div>

      {/* ── User Info Strip ── */}
      <div className="mb-5 rounded-lg bg-gray-50 px-4 py-3 dark:bg-gray-800">
        <p className="text-theme-xs text-gray-500 dark:text-gray-400">Email</p>
        <p className="text-theme-sm font-medium text-gray-800 dark:text-white/90">
          {user?.email}
        </p>
        <p className="mt-1.5 text-theme-xs text-gray-500 dark:text-gray-400">Current Role</p>
        <p className="text-theme-sm font-medium capitalize text-gray-800 dark:text-white/90">
          {user?.role}
        </p>
      </div>

      {/* ── Role Select ── */}
      <div className="mb-6">
        <label className="mb-1.5 block text-theme-sm font-medium text-gray-700 dark:text-gray-300">
          New Role <span className="text-error-500">*</span>
        </label>

        {rolesLoading ? (
          <div className="h-11 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800" />
        ) : (
          <select
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="h-11 w-full appearance-none rounded-lg border border-gray-300 px-4 py-2.5 text-sm shadow-theme-xs focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:focus:border-brand-800"
          >
            <option value="" disabled>Select a role…</option>
            {roles.map((r) => (
              <option key={r.role} value={r.role}>
                {r.label}{r.isSystem ? "" : " (Custom)"}
              </option>
            ))}
          </select>
        )}

        {selectedRole && (
          <p className="mt-1.5 text-theme-xs text-gray-400 dark:text-gray-500">
            The user will receive all permissions defined for the{" "}
            <span className="font-medium capitalize">{selectedRole}</span> role.
          </p>
        )}
      </div>

      {/* ── Actions ── */}
      <div className="flex items-center justify-end gap-3">
        <button
          onClick={handleClose}
          disabled={isLoading}
          className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-theme-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
        >
          Cancel
        </button>
        <button
          onClick={handleConfirm}
          disabled={!selectedRole || isLoading}
          className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-theme-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
        >
          {isLoading && (
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          )}
          {isLoading ? "Saving…" : "Save Role"}
        </button>
      </div>
    </Modal>
  );
}
