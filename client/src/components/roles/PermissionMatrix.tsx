"use client";

import React, { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Checkbox from "../form/input/Checkbox";
import { PermissionRow, PermissionAction } from "@/types/roles.types";

const ACTIONS: PermissionAction[] = ["view", "create", "edit", "delete"];

interface PermissionMatrixProps {
  rows:      PermissionRow[];
  isLoading: boolean;
  isDirty:   boolean;
  saving:    boolean;
  onToggle:  (rowId: string, action: PermissionAction) => void;
  onToggleRow:    (rowId: string, value: boolean) => void;   // select/clear all actions in one row
  onSelectAll:    (value: boolean) => void;                  // select/clear every cell
  onSave:    () => void;
  onDiscard: () => void;
}

export function PermissionMatrix({
  rows,
  isLoading,
  isDirty,
  saving,
  onToggle,
  onToggleRow,
  onSelectAll,
  onSave,
  onDiscard,
}: PermissionMatrixProps) {
  const t    = useTranslations("rbac.matrix");
  const tAct = useTranslations("rbac.actions");

  // ── Derived counts ─────────────────────────────────────────────────────────
  const enabledCount = useMemo(
    () => rows.reduce((acc, row) =>
      acc + ACTIONS.filter((a) => row[a]).length, 0),
    [rows],
  );

  const totalCells  = rows.length * ACTIONS.length;
  const allSelected = totalCells > 0 && enabledCount === totalCells;

  const isRowAllSelected = (row: PermissionRow) =>
    ACTIONS.every((a) => row[a]);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/[0.05] dark:bg-white/[0.03]">

      {/* ── Card header ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-5 py-4 dark:border-white/[0.05]">
        <div>
          <h2 className="text-base">{t("title")}</h2>
          <p className="text-theme-xs text-gray-400 dark:text-gray-500 mt-0.5">
            {t("hint")}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* ── Permission count pill ── */}
          {!isLoading && (
            <span className="flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-theme-xs font-medium text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
              {enabledCount} {enabledCount === 1 ? "permission" : "permissions"}
            </span>
          )}

          {/* ── Select All toggle ── */}
          {!isLoading && rows.length > 0 && (
            <button
              onClick={() => onSelectAll(!allSelected)}
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-theme-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            >
              <span
                className={`flex h-3.5 w-3.5 items-center justify-center rounded border transition-colors
                  ${allSelected
                    ? "border-brand-500 bg-brand-500"
                    : "border-gray-400 dark:border-gray-500"
                  }`}
              >
                {allSelected && (
                  <svg className="h-2.5 w-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </span>
              Select all
            </button>
          )}

          {/* ── Save / Discard ── */}
          {isDirty && (
            <>
              <button
                onClick={onDiscard}
                disabled={saving}
                className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-theme-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
              >
                {t("discard")}
              </button>
              <button
                onClick={onSave}
                disabled={saving}
                className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-theme-sm font-medium text-white hover:bg-brand-600 disabled:opacity-60 transition-colors"
              >
                {saving && (
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                )}
                {saving ? t("saving") : t("saveChanges")}
              </button>
            </>
          )}
        </div>
      </div>

      {/* ── Table ── */}
      <div className="max-w-full overflow-x-auto">
        <div className="min-w-[680px]">
          <Table>
            {/* Header */}
            <TableHeader className="border-b border-gray-100 dark:border-white/[0.05]">
              <TableRow>
                {/* Category column */}
                <TableCell
                  isHeader
                  className="w-48 text-start px-5 py-3 text-theme-xs font-medium text-gray-500 dark:text-gray-400"
                >
                  {t("category")}
                </TableCell>

                {/* All column */}
                <TableCell
                  isHeader
                  className="text-start px-5 py-3 text-theme-xs font-medium text-gray-500 dark:text-gray-400"
                >
                  All
                </TableCell>

                {/* Action columns */}
                {ACTIONS.map((action) => (
                  <TableCell
                    key={action}
                    isHeader
                    className="text-start px-5 py-3 text-theme-xs font-medium text-gray-500 dark:text-gray-400"
                  >
                    {tAct(action)}
                  </TableCell>
                ))}
              </TableRow>
            </TableHeader>

            {/* Body */}
            <TableBody className="divide-y divide-gray-100 dark:divide-white/[0.05]">
              {isLoading ? (
                <TableRow>
                  <TableCell className="px-5 py-12 text-center text-theme-sm text-gray-400 dark:text-gray-500">
                    Loading permissions…
                  </TableCell>
                </TableRow>
              ) : rows.length === 0 ? (
                <TableRow>
                  <TableCell className="px-5 py-12 text-center text-theme-sm text-gray-400 dark:text-gray-500">
                    No permissions data available
                  </TableCell>
                </TableRow>
              ) : null}

              {!isLoading && rows.map((row) => {
                const rowAllSelected = isRowAllSelected(row);
                return (
                  <TableRow
                    key={row.id}
                    className="hover:bg-gray-50/50 transition-colors dark:hover:bg-white/[0.02]"
                  >
                    {/* Category label */}
                    <TableCell className="px-5 py-4">
                      <span className="text-theme-sm font-medium text-gray-800 dark:text-white/90">
                        {row.category}
                      </span>
                    </TableCell>

                    {/* All — selects/clears every action for this row */}
                    <TableCell className="px-5 py-4">
                      <Checkbox
                        checked={rowAllSelected}
                        onChange={() => onToggleRow(row.id, !rowAllSelected)}
                      />
                    </TableCell>

                    {/* Individual action checkboxes */}
                    {ACTIONS.map((action) => (
                      <TableCell key={action} className="px-5 py-4">
                        <Checkbox
                          checked={row[action]}
                          onChange={() => onToggle(row.id, action)}
                        />
                      </TableCell>
                    ))}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
