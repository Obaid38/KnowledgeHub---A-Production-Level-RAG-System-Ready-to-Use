"use client";
import React from "react";
import { useAuthStore } from "@/store/authStore";

export default function UserMetaCard() {
  const user = useAuthStore((s) => s.user);

  const fullName = user ? `${user.firstName} ${user.lastName}`.trim() : "—";
  const role     = user?.role ?? "—";
  const initials = user
    ? `${user.firstName[0] ?? ""}${user.lastName[0] ?? ""}`.toUpperCase()
    : "?";

  return (
    <div className="p-5 border border-gray-200 rounded-2xl dark:border-gray-800 lg:p-6">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-col items-center w-full gap-6 xl:flex-row">
          {/* Avatar — initials fallback */}
          <div className="w-20 h-20 flex items-center justify-center rounded-full bg-brand-500 text-white text-xl font-bold shrink-0 border border-gray-200 dark:border-gray-800 select-none">
            {initials}
          </div>

          {/* Name & role */}
          <div className="order-3 xl:order-2">
            <h4 className="mb-2 text-lg font-semibold text-center text-gray-800 dark:text-white/90 xl:text-left">
              {fullName}
            </h4>
            <p className="text-theme-sm text-gray-500 dark:text-gray-400 text-center xl:text-left">
              {role}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
