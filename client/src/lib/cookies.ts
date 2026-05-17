// src/lib/cookies.ts
// Client-side cookie helpers for auth token storage.
// Next.js middleware reads these cookies to enforce route protection.

const TOKEN_COOKIE = "auth-token";
const ROLE_COOKIE  = "user-role";
const MAX_AGE      = 60 * 60 * 24; // 24 h — matches JWT expiry

function set(name: string, value: string, maxAge: number): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAge}; SameSite=Lax`;
}

function get(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function del(name: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; path=/; max-age=0`;
}

/** Set both auth-token and user-role cookies after a successful login. */
export function setAuthCookies(token: string, role: string | undefined): void {
  set(TOKEN_COOKIE, token, MAX_AGE);
  set(ROLE_COOKIE, (role ?? "user").toLowerCase(), MAX_AGE);
}

/** Remove auth cookies on logout. */
export function clearAuthCookies(): void {
  del(TOKEN_COOKIE);
  del(ROLE_COOKIE);
}

/** Read the JWT token from the cookie (client-side only). */
export function getTokenFromCookie(): string | null {
  return get(TOKEN_COOKIE);
}
