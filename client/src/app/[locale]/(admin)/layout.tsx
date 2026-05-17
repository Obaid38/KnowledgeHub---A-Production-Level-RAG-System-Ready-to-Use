"use client";

import { useSidebar } from "@/context/SidebarContext";
import AppHeader from "@/layout/AppHeader";
import AppSidebar from "@/layout/AppSidebar";
import Backdrop from "@/layout/Backdrop";
import React, { useEffect } from "react";
import { useAuthStore } from "@/store/authStore";
import { useRouter, useParams, usePathname } from "next/navigation";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isExpanded, isHovered, isMobileOpen } = useSidebar();
  const { user, isAuthenticated } = useAuthStore();
  const router = useRouter();
  const params = useParams();
  const pathname = usePathname();
  const locale = params?.locale ?? "en";

  const isAdmin = user?.role === "Admin" || user?.role === "SuperAdmin";
  // Strip the leading /{locale} so we can compare plain paths
  const cleanPath = pathname.replace(/^\/(en|ko)/, "") || "/";
  const isSharedRoute = cleanPath === "/profile" || cleanPath.startsWith("/profile/");

  const blocked = isAuthenticated && !isAdmin && !isSharedRoute;

  useEffect(() => {
    if (blocked) {
      router.replace(`/${locale}/error-404`);
    }
  }, [blocked, locale, router]);

  const mainContentMargin = isMobileOpen
    ? "ml-0"
    : isExpanded || isHovered
    ? "lg:ml-[290px]"
    : "lg:ml-[90px]";

  if (blocked) return null;

  return (
    <div className="min-h-screen xl:flex">
      <AppSidebar />
      <Backdrop />
      <div
        className={`flex-1 transition-all duration-300 ease-in-out ${mainContentMargin}`}
      >
        <AppHeader />
        <div className="p-4 mx-auto max-w-(--breakpoint-2xl) md:p-6">
          {children}
        </div>
      </div>
    </div>
  );
}