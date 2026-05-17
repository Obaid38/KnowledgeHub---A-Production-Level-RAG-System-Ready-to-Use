import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

// These are locale-aware drop-in replacements for next/navigation.
// Import useRouter, usePathname, Link, and redirect from here
// instead of from "next/navigation" whenever you need locale-aware behaviour.
//
// usePathname() → returns path WITHOUT locale prefix  ("/dashboard" not "/ko/dashboard")
// useRouter().replace(path, { locale }) → switches locale and navigates correctly
// Link → renders href with the correct locale prefix automatically
export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);