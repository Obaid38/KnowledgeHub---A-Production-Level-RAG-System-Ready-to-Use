"use client";

import React, { useEffect } from "react";
import ThemeTogglerTwo from "@/components/common/ThemeTogglerTwo";
import { useAuthStore } from "@/store/authStore";
import { useRouter, useParams } from "next/navigation";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated } = useAuthStore();
  const router = useRouter();
  const params = useParams();
  const locale = params?.locale ?? "en";

  const isAdmin = user?.role === "Admin" || user?.role === "SuperAdmin";
  const blocked = isAuthenticated;

  useEffect(() => {
    if (blocked) {
      router.replace(isAdmin ? `/${locale}` : `/${locale}/qa`);
    }
  }, [blocked, isAdmin, locale, router]);

  if (blocked) return null;

  return (
    <div className="relative p-6 bg-white z-1 dark:bg-gray-900 sm:p-0">
      <div className="relative flex w-full min-h-screen items-center justify-center dark:bg-gray-900">
        <div className="w-full max-w-lg px-4 py-10">
          {children}
        </div>
        <div className="fixed bottom-6 right-6 z-50 hidden sm:block">
          <ThemeTogglerTwo />
        </div>
      </div>
    </div>
  );
}
