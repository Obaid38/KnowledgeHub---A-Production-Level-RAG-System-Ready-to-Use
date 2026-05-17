// src/services/auth.service.ts
//
// ALL authentication API calls live here.
// Components and the Zustand store import from this file only —
// never call axios directly from a component or store action.

import { publicAxios, privateAxios } from "@/lib/axios";
import type { PermissionRow } from "@/types/roles.types";

// ─── Request / response types ─────────────────────────────────────────────────

export interface LoginRequest {
  email:    string;
  password: string;
}

/** When MFA is NOT enabled — backend returns a full session immediately. */
export interface LoginSuccessResponse {
  mfaRequired: false;
  user:        AuthUser;
  token:       string;
}

/** When MFA IS enabled — a short-lived mfaToken is returned for the verify step. */
export interface LoginMfaRequiredResponse {
  mfaRequired: true;
  mfaToken:    string;
  email:       string;
}

export type LoginResponse = LoginSuccessResponse | LoginMfaRequiredResponse;

export interface VerifyMfaRequest {
  mfaToken: string;
  code:     string;
}

export interface VerifyRecoveryRequest {
  mfaToken:     string;
  recoveryCode: string;
}

export interface MfaVerifiedResponse {
  user:  AuthUser;
  token: string;
}

export interface SignUpRequest {
  firstName: string;
  lastName:  string;
  email:     string;
  password:  string;
}

export interface SignUpResponse {
  message: string;
  user:    AuthUser;
}

export interface ForgotPasswordRequest { email: string; }
export interface ResetPasswordRequest  { token: string; password: string; }

export interface AuthUser {
  id:          string;
  email:       string;
  firstName:   string;
  lastName:    string;
  role:        string;
  mfaEnabled:  boolean;
  /** Permission matrix for this user's role, returned by the backend on every auth response. */
  permissions: PermissionRow[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Backend's userPublic() returns _id (Mongo ObjectId), not id.
 * Normalise so the frontend always sees `id`.
 */
function normaliseUser(raw: Record<string, unknown>): AuthUser {
  return {
    id:          ((raw._id ?? raw.id) as string) ?? "",
    email:       (raw.email      as string)  ?? "",
    firstName:   (raw.firstName  as string)  ?? "",
    lastName:    (raw.lastName   as string)  ?? "",
    role:        (raw.role       as string)  ?? "User",
    mfaEnabled:  (raw.mfaEnabled as boolean) ?? false,
    permissions: (raw.permissions as PermissionRow[]) ?? [],
  };
}

// ─── Service functions ────────────────────────────────────────────────────────

/** Login with email + password. Returns a full session or an MFA challenge. */
export async function loginApi(payload: LoginRequest): Promise<LoginResponse> {
  const { data } = await publicAxios.post<Record<string, unknown>>("/auth/login", payload);
  if (data.mfaRequired) {
    return data as unknown as LoginMfaRequiredResponse;
  }
  return {
    mfaRequired: false,
    token: data.token as string,
    user:  normaliseUser(data.user as Record<string, unknown>),
  };
}

/** Verify the 6-digit TOTP code when MFA is enabled. */
export async function verifyMfaApi(payload: VerifyMfaRequest): Promise<MfaVerifiedResponse> {
  const { data } = await publicAxios.post<Record<string, unknown>>("/auth/verify-mfa", payload);
  return {
    token: data.token as string,
    user:  normaliseUser(data.user as Record<string, unknown>),
  };
}

/** Verify a recovery code instead of TOTP. */
export async function verifyMfaRecoveryApi(payload: VerifyRecoveryRequest): Promise<MfaVerifiedResponse> {
  const { data } = await publicAxios.post<Record<string, unknown>>("/auth/verify-mfa-recovery", payload);
  return {
    token: data.token as string,
    user:  normaliseUser(data.user as Record<string, unknown>),
  };
}

/** Register a new user account. */
export async function signUpApi(payload: SignUpRequest): Promise<SignUpResponse> {
  const { data } = await publicAxios.post<SignUpResponse>("/auth/register", payload);
  return data;
}

/** Send a password-reset email. */
export async function forgotPasswordApi(payload: ForgotPasswordRequest): Promise<{ message: string }> {
  const { data } = await publicAxios.post<{ message: string }>("/auth/forgot-password", payload);
  return data;
}

/** Reset password using the token from the reset email. */
export async function resetPasswordApi(payload: ResetPasswordRequest): Promise<{ message: string }> {
  const { data } = await publicAxios.post<{ message: string }>("/auth/reset-password", payload);
  return data;
}

// ─── Profile ──────────────────────────────────────────────────────────────────

export interface UpdateProfileRequest {
  firstName?: string;
  lastName?:  string;
}

/** POST /auth/change-password — change the current user's password. */
export async function changePasswordApi(payload: {
  currentPassword: string;
  newPassword:     string;
}): Promise<{ message: string }> {
  const { data } = await privateAxios.post<{ message: string }>("/auth/change-password", payload);
  return data;
}

/** PATCH /auth/me — update firstName / lastName. Returns the updated user. */
export async function updateProfileApi(payload: UpdateProfileRequest): Promise<AuthUser> {
  const { data } = await privateAxios.patch<{ user: Record<string, unknown> }>("/auth/me", payload);
  const u = data.user ?? (data as unknown as Record<string, unknown>);
  return normaliseUser(u as Record<string, unknown>);
}

// ─── MFA ─────────────────────────────────────────────────────────────────────

export interface MfaSetupResponse {
  secret:  string;
  qrCode:  string;   // base64 data-URL from the backend
}

export interface MfaEnableResponse {
  message:       string;
  recoveryCodes: string[];
}

/** POST /auth/mfa/setup — generate a new TOTP secret + QR code. */
export async function mfaSetupApi(): Promise<MfaSetupResponse> {
  const { data } = await privateAxios.post<MfaSetupResponse>("/auth/mfa/setup");
  return data;
}

/** POST /auth/mfa/enable — verify TOTP code and activate MFA, returns recovery codes. */
export async function mfaEnableApi(code: string): Promise<MfaEnableResponse> {
  const { data } = await privateAxios.post<MfaEnableResponse>("/auth/mfa/enable", { code });
  return data;
}

/** POST /auth/mfa/disable — verify TOTP code and deactivate MFA. */
export async function mfaDisableApi(code: string): Promise<{ message: string }> {
  const { data } = await privateAxios.post<{ message: string }>("/auth/mfa/disable", { code });
  return data;
}
export async function getProfileApi(): Promise<AuthUser> {
  const { data } = await privateAxios.get<{ user: Record<string, unknown> }>("/auth/me");
  const u = data.user ?? (data as unknown as Record<string, unknown>);
  return normaliseUser(u as Record<string, unknown>);
}
