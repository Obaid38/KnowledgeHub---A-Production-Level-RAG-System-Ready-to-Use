"use client";

import React from "react";
import { useTranslations } from "next-intl";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Badge from "@/components/ui/badge/Badge";
import { User, UserFilterTab } from "@/types/users";

interface UsersTableProps {
  users:           User[];
  activeTab:       UserFilterTab;
  onApprove:       (user: User) => void;   // Opens the role-assignment modal
  onReject:        (id: string) => void;
  onEditRole:      (user: User) => void;   // Opens the edit-role modal
  onDelete:        (user: User) => void;   // Opens the delete confirm modal
  actionLoading:   string | null;          // id of the user currently being actioned
}

const COLUMNS = ["sn", "firstName", "lastName", "email", "role", "verified", "createdAt", "actions"] as const;

/** Format an ISO date string to a readable date like "Apr 13, 2026". */
function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year:  "numeric",
      month: "short",
      day:   "numeric",
    });
  } catch {
    return iso;
  }
}

export function UsersTable({
  users,
  activeTab,
  onApprove,
  onReject,
  onEditRole,
  onDelete,
  actionLoading,
}: UsersTableProps) {
  const t = useTranslations("users.table");

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/5 dark:bg-white/3">
      <div className="max-w-full overflow-x-auto">
        <div className="min-w-[960px]">
          <Table>
            {/* ── Header ── */}
            <TableHeader className="border-b border-gray-100 dark:border-white/5">
              <TableRow>
                {COLUMNS.map((col) => (
                  <TableCell
                    key={col}
                    isHeader
                    className="bg-brand-500 px-5 py-3 text-left text-theme-xs font-semibold uppercase tracking-wide text-white first:rounded-tl-xl last:rounded-tr-xl dark:bg-brand-600"
                  >
                    {t(`columns.${col}`)}
                  </TableCell>
                ))}
              </TableRow>
            </TableHeader>

            {/* ── Body ── */}
            <TableBody className="divide-y divide-gray-100 dark:divide-white/5">
              {users.length === 0 ? (
                <TableRow>
                  <TableCell className="px-5 py-12 text-center text-theme-sm text-gray-400 dark:text-gray-500">
                    {t("noUsers")}
                  </TableCell>
                </TableRow>
              ) : (
                users.map((user, idx) => (
                  <TableRow
                    key={user.id}
                    className="transition-colors hover:bg-gray-50/50 dark:hover:bg-white/2"
                  >
                    {/* S/N */}
                    <TableCell className="px-5 py-4 text-theme-sm text-gray-500 dark:text-gray-400">
                      {idx + 1}
                    </TableCell>

                    {/* First Name */}
                    <TableCell className="px-5 py-4 text-theme-sm font-medium text-gray-800 dark:text-white/90">
                      {user.firstName}
                    </TableCell>

                    {/* Last Name */}
                    <TableCell className="px-5 py-4 text-theme-sm text-gray-700 dark:text-gray-300">
                      {user.lastName}
                    </TableCell>

                    {/* Email */}
                    <TableCell className="px-5 py-4 text-theme-sm text-gray-600 dark:text-gray-400">
                      {user.email}
                    </TableCell>

                    {/* Role */}
                    <TableCell className="px-5 py-4 text-theme-sm text-gray-600 dark:text-gray-400">
                      {user.role}
                    </TableCell>

                    {/* Verified badge */}
                    <TableCell className="px-5 py-4">
                      <Badge
                        size="sm"
                        variant="light"
                        color={user.verified === "Verified" ? "success" : "warning"}
                      >
                        {user.verified === "Verified"
                          ? t("verified")
                          : t("unverified")}
                      </Badge>
                    </TableCell>

                    {/* Created At */}
                    <TableCell className="px-5 py-4 text-theme-sm text-gray-500 dark:text-gray-400">
                      {formatDate(user.createdAt)}
                    </TableCell>

                    {/* Actions */}
                    <TableCell className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        {user.verified === "Unverified" ? (
                          /* ── Unverified user: Approve + Reject ── */
                          <>
                            <button
                              onClick={() => onApprove(user)}
                              disabled={actionLoading === user.id}
                              className="rounded-lg bg-success-500 px-3 py-1.5 text-theme-xs font-semibold text-white transition-colors hover:bg-success-600 disabled:opacity-60"
                            >
                              {actionLoading === user.id ? "…" : t("approve")}
                            </button>
                            <button
                              onClick={() => onReject(user.id)}
                              disabled={actionLoading === user.id}
                              className="rounded-lg bg-warning-500 px-3 py-1.5 text-theme-xs font-semibold text-white transition-colors hover:bg-warning-600 disabled:opacity-60"
                            >
                              {actionLoading === user.id ? "…" : t("reject")}
                            </button>
                          </>
                        ) : (
                          /* ── Verified user: Edit Role ── */
                          <button
                            onClick={() => onEditRole(user)}
                            disabled={actionLoading === user.id}
                            className="rounded-lg bg-brand-500 px-3 py-1.5 text-theme-xs font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-60"
                          >
                            {t("editRole")}
                          </button>
                        )}

                        {/* ── Delete (always visible) ── */}
                        <button
                          onClick={() => onDelete(user)}
                          disabled={actionLoading === user.id}
                          className="rounded-lg bg-error-500 px-3 py-1.5 text-theme-xs font-semibold text-white transition-colors hover:bg-error-600 disabled:opacity-60"
                        >
                          {t("delete")}
                        </button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
