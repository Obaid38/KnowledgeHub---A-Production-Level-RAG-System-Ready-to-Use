"use client";

import React from "react";
import { SystemRole, RoleDefinition } from "@/types/roles.types";

interface RoleTabBarProps {
  active:   SystemRole;
  roles:    RoleDefinition[];
  onChange: (role: SystemRole) => void;
}

export function RoleTabBar({ active, roles, onChange }: RoleTabBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {roles.map(({ role, label, permissionCount, userCount }) => {
        const isActive = active === role;

        return (
          <button
            key={role}
            onClick={() => onChange(role)}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-theme-sm font-medium transition-all duration-150
              ${
                isActive
                  ? "bg-brand-500 text-white shadow-theme-xs"
                  : "border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
              }
            `}
          >
            <span>{label}</span>

            {/* Permission count pill */}
            <span
              className={`rounded-full px-2 py-0.5 text-theme-xs font-normal tabular-nums
                ${
                  isActive
                    ? "bg-white/20 text-white"
                    : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                }
              `}
            >
              {permissionCount} {permissionCount === 1 ? "permission" : "permissions"}
            </span>

            {/* User count pill */}
            <span
              className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-theme-xs font-normal tabular-nums
                ${
                  isActive
                    ? "bg-white/20 text-white"
                    : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                }
              `}
            >
              <svg className="h-3 w-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M17 20h5v-2a4 4 0 00-4-4h-1M9 20H4v-2a4 4 0 014-4h1m4-4a4 4 0 110-8 4 4 0 010 8z" />
              </svg>
              {userCount}
            </span>
          </button>
        );
      })}
    </div>
  );
}
