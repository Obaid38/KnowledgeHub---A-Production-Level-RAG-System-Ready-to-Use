"use client";

import React from "react";
import Modal from "@/components/ui/modal";
import { User } from "@/types/users";

interface DeleteConfirmModalProps {
  isOpen:    boolean;
  user:      User | null;
  onClose:   () => void;
  onConfirm: (userId: string) => void;
  isLoading: boolean;
}

export function DeleteConfirmModal({
  isOpen,
  user,
  onClose,
  onConfirm,
  isLoading,
}: DeleteConfirmModalProps) {
  const fullName = user ? `${user.firstName} ${user.lastName}` : "";

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="max-w-md"
      showCloseButton
    >
      {/* ── Header ── */}
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          Delete User
        </h2>
        <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
          This action cannot be undone.
        </p>
      </div>

      {/* ── Warning Strip ── */}
      <div className="mb-6 rounded-lg border border-error-200 bg-error-50 px-4 py-3 dark:border-error-500/20 dark:bg-error-500/10">
        <p className="text-theme-sm text-error-700 dark:text-error-400">
          Are you sure you want to permanently delete{" "}
          <span className="font-semibold">{fullName}</span>{" "}
          ({user?.email})? All their data will be removed.
        </p>
      </div>

      {/* ── Actions ── */}
      <div className="flex items-center justify-end gap-3">
        <button
          onClick={onClose}
          disabled={isLoading}
          className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-theme-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
        >
          Cancel
        </button>
        <button
          onClick={() => user && onConfirm(user.id)}
          disabled={isLoading}
          className="flex items-center gap-2 rounded-lg bg-error-500 px-4 py-2 text-theme-sm font-semibold text-white transition-colors hover:bg-error-600 disabled:opacity-50"
        >
          {isLoading && (
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          )}
          {isLoading ? "Deleting…" : "Delete User"}
        </button>
      </div>
    </Modal>
  );
}
