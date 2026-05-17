"use client";

import React, { useState } from "react";
import Modal from "@/components/ui/modal";

interface CreateRoleModalProps {
  isOpen:    boolean;
  onClose:   () => void;
  onConfirm: (role: string, label: string) => void;
  isLoading: boolean;
}

export function CreateRoleModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading,
}: CreateRoleModalProps) {
  const [label, setLabel] = useState("");
  const [key,   setKey]   = useState("");
  const [keyTouched, setKeyTouched] = useState(false);

  // Auto-generate role key from label (lowercase, hyphenated)
  const handleLabelChange = (val: string) => {
    setLabel(val);
    if (!keyTouched) {
      setKey(val.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""));
    }
  };

  const handleKeyChange = (val: string) => {
    setKeyTouched(true);
    setKey(val.toLowerCase().replace(/[^a-z0-9-]/g, ""));
  };

  const handleConfirm = () => {
    if (!label.trim() || !key.trim()) return;
    onConfirm(key.trim(), label.trim());
  };

  const handleClose = () => {
    setLabel("");
    setKey("");
    setKeyTouched(false);
    onClose();
  };

  const keyValid = /^[a-z][a-z0-9-]{1,39}$/.test(key);

  return (
    <Modal isOpen={isOpen} onClose={handleClose} maxWidth="max-w-md" showCloseButton>
      {/* ── Header ── */}
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          Create New Role
        </h2>
        <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
          Custom roles can have any permissions you configure after creation.
        </p>
      </div>

      {/* ── Label ── */}
      <div className="mb-4">
        <label className="mb-1.5 block text-theme-sm font-medium text-gray-700 dark:text-gray-300">
          Role Name <span className="text-error-500">*</span>
        </label>
        <input
          type="text"
          value={label}
          onChange={(e) => handleLabelChange(e.target.value)}
          placeholder="e.g. Department Head"
          className="h-11 w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
        />
      </div>

      {/* ── Key ── */}
      <div className="mb-6">
        <label className="mb-1.5 block text-theme-sm font-medium text-gray-700 dark:text-gray-300">
          Role Key <span className="text-error-500">*</span>
        </label>
        <input
          type="text"
          value={key}
          onChange={(e) => handleKeyChange(e.target.value)}
          placeholder="e.g. department-head"
          className={`h-11 w-full rounded-lg border px-4 py-2.5 text-sm shadow-theme-xs placeholder:text-gray-400 focus:outline-none focus:ring-3 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30
            ${key && !keyValid
              ? "border-error-300 focus:border-error-300 focus:ring-error-500/10"
              : "border-gray-300 focus:border-brand-300 focus:ring-brand-500/10 dark:border-gray-700 dark:focus:border-brand-800"
            }`}
        />
        <p className={`mt-1.5 text-theme-xs ${key && !keyValid ? "text-error-500" : "text-gray-400 dark:text-gray-500"}`}>
          {key && !keyValid
            ? "Must start with a letter, use only lowercase letters, numbers, and hyphens (2–40 chars)."
            : "Lowercase letters, numbers, and hyphens only. Auto-generated from name."}
        </p>
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
          disabled={!label.trim() || !keyValid || isLoading}
          className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-theme-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
        >
          {isLoading && (
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          )}
          {isLoading ? "Creating…" : "Create Role"}
        </button>
      </div>
    </Modal>
  );
}
