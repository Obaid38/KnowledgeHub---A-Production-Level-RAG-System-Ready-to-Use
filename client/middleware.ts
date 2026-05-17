import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";
import { routing } from "./src/i18n/routing";

const intlMiddleware = createMiddleware(routing);

// ─── Route definitions ────────────────────────────────────────────────────────

/** Routes accessible to regular users only (non-admin). */
const USER_ONLY_ROUTES  = ["/documents", "/qa"];

/** Routes accessible to admins only. */
const ADMIN_ONLY_ROUTES = ["/", "/users", "/roles", "/system-monitoring"];

/** Routes accessible to any authenticated user (admin + user). */
const SHARED_AUTH_ROUTES = ["/profile"];

/** Public auth pages — redirect to home if already logged in. */
const PUBLIC_AUTH = ["/signin", "/signup", "/mfa", "/forgot-password", "/reset-password"];

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Strip the leading /{locale} segment from the pathname. */
function stripLocale(pathname: string): string {
  return pathname.replace(/^\/(en|ko)/, "") || "/";
}

function matchesAny(pathname: string, routes: string[]): boolean {
  return routes.some((r) => pathname === r || pathname.startsWith(r + "/"));
}

function isAdminRole(role: string | undefined): boolean {
  const r = role?.toLowerCase();
  return r === "admin" || r === "superadmin";
}

function isSuperAdmin(role: string | undefined): boolean {
  return role?.toLowerCase() === "superadmin";
}

// ─── Middleware ───────────────────────────────────────────────────────────────

export default function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  const clean        = stripLocale(pathname);
  const locale       = pathname.split("/")[1] || "en";

  const token = request.cookies.get("auth-token")?.value;
  const role  = request.cookies.get("user-role")?.value;
  const admin = isAdminRole(role);

  const isPublicAuth     = matchesAny(clean, PUBLIC_AUTH);
  const isUserOnlyRoute  = matchesAny(clean, USER_ONLY_ROUTES);
  const isAdminOnlyRoute = matchesAny(clean, ADMIN_ONLY_ROUTES);
  const isSharedRoute    = matchesAny(clean, SHARED_AUTH_ROUTES);
  const isProtectedRoute = isUserOnlyRoute || isAdminOnlyRoute || isSharedRoute;

  // ① Authenticated non-admin hitting the locale root (/en or /en/) → /qa
  if (token && !admin && (pathname === `/${locale}` || pathname === `/${locale}/`)) {
    return NextResponse.redirect(new URL(`/${locale}/qa`, request.url));
  }

  // ② Authenticated user hitting a public-auth page → redirect to their home
  if (token && isPublicAuth) {
    const dest = admin ? `/${locale}` : `/${locale}/qa`;
    return NextResponse.redirect(new URL(dest, request.url));
  }

  // ③ Unauthenticated user hitting any protected route → sign-in
  if (!token && isProtectedRoute) {
    return NextResponse.redirect(new URL(`/${locale}/signin`, request.url));
  }

  // ④ Authenticated non-admin hitting an admin-only route → 404
  if (token && !admin && isAdminOnlyRoute) {
    return NextResponse.redirect(new URL(`/${locale}/error-404`, request.url));
  }

  // ⑤ Authenticated admin (non-superadmin) hitting a user-only route → 404
  if (token && admin && !isSuperAdmin(role) && isUserOnlyRoute) {
    return NextResponse.redirect(new URL(`/${locale}/error-404`, request.url));
  }

  // Otherwise hand off to the next-intl locale middleware 
  return intlMiddleware(request);
}
 
export const config = {
  // Match all paths except Next.js internals, static files, and API routes
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
