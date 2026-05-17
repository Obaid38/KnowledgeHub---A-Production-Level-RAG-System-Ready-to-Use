"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { useSidebar } from "../context/SidebarContext";
import {
  ChevronDownIcon,
  GridIcon,
  HorizontaLDots,
  UserCircleIcon,
  DocsIcon,
  ChatIcon,
  GroupIcon,
  LockIcon,
} from "../icons/index";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/Navigation";
import Logo from "@/components/common/Logo";
import Image from "next/image";
import { useAuthStore } from "@/store/authStore";
import { brandConfig } from "@/config/companyProfile";

const Ico = ({ icon }: { icon: any }) => {
  const C = icon?.default ?? icon;
  return <C />;
};

type NavItem = {
  name: string;
  icon: any;
  path?: string;
  subItems?: { name: string; path: string; pro?: boolean; new?: boolean }[];
};

const AppSidebar: React.FC = () => {
  const { isExpanded, isMobileOpen, isHovered, setIsHovered } = useSidebar();
  const pathname = usePathname();
  const { user, isProfileReady } = useAuthStore();

  const t = useTranslations("nav");

  const isAdmin = user?.role === "Admin" || user?.role === "SuperAdmin";
  const isSuperAdmin = user?.role === "SuperAdmin";

  const adminItems: NavItem[] = [
    { icon: GridIcon,        name: t("dashboard"),       path: "/" },
    { icon: LockIcon,        name: t("roles"),            path: "/roles" },
    { icon: GroupIcon,       name: t("userManagement"),   path: "/users" },
    { icon: UserCircleIcon,  name: t("userProfile"),      path: "/profile" },
    { icon: UserCircleIcon,  name: t("systemMonitoring"), path: "/system-monitoring" },
  ];

  const userItems: NavItem[] = [
    { icon: DocsIcon,        name: t("documents"),  path: "/documents" },
    { icon: ChatIcon,        name: t("qa"),         path: "/qa" },
    { icon: UserCircleIcon,  name: t("userProfile"), path: "/profile" },
  ];

  const superAdminItems: NavItem[] = [
    { icon: GridIcon,        name: t("dashboard"),       path: "/" },
    { icon: LockIcon,        name: t("roles"),            path: "/roles" },
    { icon: GroupIcon,       name: t("userManagement"),   path: "/users" },
    { icon: UserCircleIcon,  name: t("systemMonitoring"), path: "/system-monitoring" },
    { icon: DocsIcon,        name: t("documents"),        path: "/documents" },
    { icon: ChatIcon,        name: t("qa"),               path: "/qa" },
    { icon: UserCircleIcon,  name: t("userProfile"),      path: "/profile" },
  ];

  const navItems: NavItem[] = isSuperAdmin ? superAdminItems : isAdmin ? adminItems : userItems;

  const [openSubmenu, setOpenSubmenu] = useState<{
    type: "main" | "others";
    index: number;
  } | null>(null);
  const [subMenuHeight, setSubMenuHeight] = useState<Record<string, number>>({});
  const subMenuRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const isActive = useCallback(
    (path: string) => pathname === path,
    [pathname],
  );

  useEffect(() => {
    let submenuMatched = false;
    (["main", "others"] as const).forEach((menuType) => {
      const items = menuType === "main" ? navItems : [];
      items.forEach((nav, index) => {
        if (nav.subItems) {
          nav.subItems.forEach((subItem) => {
            if (isActive(subItem.path)) {
              setOpenSubmenu({ type: menuType, index });
              submenuMatched = true;
            }
          });
        }
      });
    });
    if (!submenuMatched) setOpenSubmenu(null);
  }, [pathname]);

  useEffect(() => {
    if (openSubmenu !== null) {
      const key = `${openSubmenu.type}-${openSubmenu.index}`;
      if (subMenuRefs.current[key]) {
        setSubMenuHeight((prev) => ({
          ...prev,
          [key]: subMenuRefs.current[key]?.scrollHeight || 0,
        }));
      }
    }
  }, [openSubmenu]);

  const handleSubmenuToggle = (index: number, menuType: "main" | "others") => {
    setOpenSubmenu((prev) =>
      prev?.type === menuType && prev?.index === index
        ? null
        : { type: menuType, index },
    );
  };

  // ── Render helpers ────────────────────────────────────────────────────────
  const renderMenuItems = (items: NavItem[], menuType: "main" | "others") => (
    <ul className="flex flex-col gap-4">
      {items.map((nav, index) => {
        const isSubmenuOpen =
          openSubmenu?.type === menuType && openSubmenu?.index === index;

        return (
          <li key={nav.name}>
            {nav.subItems ? (
              // ── Has children → expand/collapse button ──
              <button
                onClick={() => handleSubmenuToggle(index, menuType)}
                className={`menu-item group ${
                  isSubmenuOpen ? "menu-item-active" : "menu-item-inactive"
                } cursor-pointer ${
                  !isExpanded && !isHovered ? "lg:justify-center" : "lg:justify-start"
                }`}
              >
                <span
                  className={
                    isSubmenuOpen
                      ? "menu-item-icon-active"
                      : "menu-item-icon-inactive"
                  }
                >
                  <Ico icon={nav.icon} />
                </span>
                {(isExpanded || isHovered || isMobileOpen) && (
                  <>
                    <span className="menu-item-text">{nav.name}</span>
                    <ChevronDownIcon
                      className={`ml-auto w-5 h-5 transition-transform duration-200 ${
                        isSubmenuOpen ? "rotate-180 text-brand-500" : ""
                      }`}
                    />
                  </>
                )}
              </button>
            ) : (
              // ── No children → direct Link ──
              nav.path && (
                <Link
                  href={nav.path}
                  className={`menu-item group ${
                    isActive(nav.path) ? "menu-item-active" : "menu-item-inactive"
                  } ${
                    !isExpanded && !isHovered
                      ? "lg:justify-center"
                      : "lg:justify-start"
                  }`}
                >
                  <span
                    className={
                      isActive(nav.path)
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                  >
                    <Ico icon={nav.icon} />
                  </span>
                  {(isExpanded || isHovered || isMobileOpen) && (
                    <span className="menu-item-text">{nav.name}</span>
                  )}
                </Link>
              )
            )}

            {/* Submenu dropdown */}
            {nav.subItems && (
              <div
                ref={(el) => {
                  subMenuRefs.current[`${menuType}-${index}`] = el;
                }}
                className="overflow-hidden transition-all duration-300"
                style={{
                  height: isSubmenuOpen
                    ? `${subMenuHeight[`${menuType}-${index}`]}px`
                    : "0px",
                }}
              >
                <ul className="mt-2 space-y-1 ml-9">
                  {nav.subItems.map((subItem) => (
                    <li key={subItem.name}>
                      <Link
                        href={subItem.path}
                        className={`menu-dropdown-item ${
                          isActive(subItem.path)
                            ? "menu-dropdown-item-active"
                            : "menu-dropdown-item-inactive"
                        }`}
                      >
                        {subItem.name}
                        {subItem.new && (
                          <span className="ml-auto text-xs font-medium text-brand-500 bg-brand-50 dark:bg-brand-500/10 px-2 py-0.5 rounded-full">
                            new
                          </span>
                        )}
                        {subItem.pro && (
                          <span className="ml-auto text-xs font-medium text-brand-500 bg-brand-50 dark:bg-brand-500/10 px-2 py-0.5 rounded-full">
                            pro
                          </span>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );

  // ── Sidebar shell ─────────────────────────────────────────────────────────
  return (
    <aside
      className={`fixed mt-16 flex flex-col lg:mt-0 top-0 px-5 left-0 bg-white dark:bg-gray-900 dark:border-gray-800 text-gray-900 h-screen transition-all duration-300 ease-in-out z-50 border-r border-gray-200
        ${
          isExpanded || isMobileOpen
            ? "w-[290px]"
            : isHovered
              ? "w-[290px]"
              : "w-[90px]"
        }
        ${isMobileOpen ? "translate-x-0" : "-translate-x-full"}
        lg:translate-x-0`}
      onMouseEnter={() => !isExpanded && setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Logo */}
      <div className="mt-5">
       {isExpanded || isHovered || isMobileOpen ? (
  <Logo />
) : (
          <div>
          <Image
                  src={brandConfig.logo_light_path}
                  alt={brandConfig.app_name}
                  width={100}
                  height={100}
                  className="dark:hidden"
                />
                <Image
                  src={brandConfig.logo_dark_path}
                  alt={brandConfig.app_name}
                  width={100}
                  height={100}
                  className="hidden dark:block"
                />
            </div>
        )}
      </div>

      {/* Nav */}
      <div className="flex flex-col overflow-y-auto duration-300 ease-linear no-scrollbar">
        <nav className="mb-6">
          <div className="flex flex-col gap-4">
            <div>
              <h2
                className={`mb-4 text-xs uppercase flex text-gray-400 ${
                  !isExpanded && !isHovered
                    ? "lg:justify-center"
                    : "justify-start"
                }`}
              >
                {isExpanded || isHovered || isMobileOpen ? (
                  t("mainMenu")
                ) : (
                  <HorizontaLDots />
                )}
              </h2>
              {!isProfileReady ? (
                <ul className="flex flex-col gap-4">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <li key={i} className="flex items-center gap-3 px-3 py-2">
                      {/* icon placeholder */}
                      <div className="h-6 w-6 rounded-md bg-gray-200 dark:bg-gray-700 animate-pulse shrink-0" />
                      {(isExpanded || isHovered || isMobileOpen) && (
                        <div
                          className="h-4 rounded bg-gray-200 dark:bg-gray-700 animate-pulse"
                          style={{ width: `${55 + (i % 3) * 20}%` }}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                renderMenuItems(navItems, "main")
              )}
            </div>
          </div>
        </nav>
      </div>
    </aside>
  );
};

export default AppSidebar;
