// src/store/authStore.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  loginApi,
  verifyMfaApi,
  verifyMfaRecoveryApi,
  signUpApi,
  forgotPasswordApi,
  resetPasswordApi,
  type AuthUser,
  type LoginRequest,
  type SignUpRequest,
  type VerifyMfaRequest,
  type VerifyRecoveryRequest,
  type ForgotPasswordRequest,
  type ResetPasswordRequest,
} from "@/services/auth.service";
import { setAuthCookies, clearAuthCookies } from "@/lib/cookies";
import type { PermissionRow } from "@/types/roles.types";

interface AuthState {
  user:             AuthUser | null;
  token:            string | null;
  isAuthenticated:  boolean;
  pendingEmail:     string | null;
  pendingMfaToken:  string | null;
  isLoading:        boolean;
  error:            string | null;
  /**
   * True once the profile has been confirmed (login, MFA, setUser, or logout).
   * Starts false on every page boot so the sidebar/header can show skeletons
   * while AuthInitializer's /auth/me call is in-flight.
   * NOT persisted to localStorage.
   */
  isProfileReady:   boolean;
  /** The current user's permission matrix, fetched from the RBAC API on login. */
  permissions:      PermissionRow[];
}

interface AuthActions {
  login:              (payload: LoginRequest)        => Promise<LoginResult>;
  verifyMfa:          (code: string)                 => Promise<void>;
  verifyMfaRecovery:  (recoveryCode: string)         => Promise<void>;
  signUp:             (payload: SignUpRequest)        => Promise<void>;
  forgotPassword:     (payload: ForgotPasswordRequest) => Promise<void>;
  resetPassword:      (payload: ResetPasswordRequest)  => Promise<void>;
  logout:             ()                             => void;
  clearError:         ()                             => void;
  setUser:            (user: AuthUser, token: string) => void;
  /** Flip isProfileReady to true with no other side-effects (no cookie clearing). */
  setProfileReady:    ()                             => void;
  /** Merge partial user fields into the store without re-fetching from the server. */
  updateUserLocally:  (updates: Partial<AuthUser>)  => void;
}

export type LoginResult =
  | { status: "success" }
  | { status: "mfa_required" };

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set, get) => ({
      // ── Initial state ──────────────────────────────────────────────────────
      user:            null,
      token:           null,
      isAuthenticated: false,
      pendingEmail:    null,
      pendingMfaToken: null,
      isLoading:       false,
      error:           null,
      isProfileReady:  false,
      permissions:     [],

      // ── Actions ────────────────────────────────────────────────────────────

      login: async (payload) => {
        set({ isLoading: true, error: null });
        try {
          const data = await loginApi(payload);

          if (data.mfaRequired) {
            set({
              pendingEmail:    data.email,
              pendingMfaToken: data.mfaToken,
              isLoading:       false,
            });
            return { status: "mfa_required" };
          }

          // Store token in cookie so middleware can read it for route protection
          setAuthCookies(data.token, data.user.role);

          set({
            user:            data.user,
            token:           data.token,
            isAuthenticated: true,
            pendingEmail:    null,
            pendingMfaToken: null,
            isLoading:       false,
            isProfileReady:  true,
            permissions:     data.user.permissions ?? [],
          });
          return { status: "success" };
        } catch (err) {
          const message = err instanceof Error ? err.message : "Login failed.";
          set({ isLoading: false, error: message });
          throw err;
        }
      },
      

      verifyMfa: async (code) => {
        const { pendingMfaToken } = get();
        if (!pendingMfaToken) throw new Error("No pending MFA session.");

        set({ isLoading: true, error: null });
        try {
          const data = await verifyMfaApi({ mfaToken: pendingMfaToken, code });

          setAuthCookies(data.token, data.user.role);

          set({
            user:            data.user,
            token:           data.token,
            isAuthenticated: true,
            pendingEmail:    null,
            pendingMfaToken: null,
            isLoading:       false,
            isProfileReady:  true,
            permissions:     data.user.permissions ?? [],
          });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Invalid code.";
          set({ isLoading: false, error: message });
          throw err;
        }
      },

      verifyMfaRecovery: async (recoveryCode) => {
        const { pendingMfaToken } = get();
        if (!pendingMfaToken) throw new Error("No pending MFA session.");

        set({ isLoading: true, error: null });
        try {
          const data = await verifyMfaRecoveryApi({ mfaToken: pendingMfaToken, recoveryCode });

          setAuthCookies(data.token, data.user.role);

          set({
            user:            data.user,
            token:           data.token,
            isAuthenticated: true,
            pendingEmail:    null,
            pendingMfaToken: null,
            isLoading:       false,
            isProfileReady:  true,
            permissions:     data.user.permissions ?? [],
          });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Invalid recovery code.";
          set({ isLoading: false, error: message });
          throw err;
        }
      },

      signUp: async (payload) => {
        set({ isLoading: true, error: null });
        try {
          await signUpApi(payload);
          set({ isLoading: false });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Registration failed.";
          set({ isLoading: false, error: message });
          throw err;
        }
      },

      forgotPassword: async (payload) => {
        set({ isLoading: true, error: null });
        try {
          await forgotPasswordApi(payload);
          set({ isLoading: false });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to send reset link.";
          set({ isLoading: false, error: message });
          throw err;
        }
      },

      resetPassword: async (payload) => {
        set({ isLoading: true, error: null });
        try {
          await resetPasswordApi(payload);
          set({ isLoading: false });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to reset password.";
          set({ isLoading: false, error: message });
          throw err;
        }
      },

      logout: () => {
        clearAuthCookies();
        set({
          user:            null,
          token:           null,
          isAuthenticated: false,
          pendingEmail:    null,
          pendingMfaToken: null,
          error:           null,
          isProfileReady:  true,
          permissions:     [],
        });
      },

      /** Used by AuthInitializer to sync /auth/me profile data into the store. */
      setUser: (user, token) => {
        setAuthCookies(token, user.role);
        set({ user, token, isAuthenticated: true, isProfileReady: true, permissions: user.permissions ?? [] });
      },

      /** Merge partial fields into the current user object — no API call. */
      updateUserLocally: (updates) => {
        set((state) => ({
          user: state.user ? { ...state.user, ...updates } : state.user,
        }));
      },

      setProfileReady: () => set({ isProfileReady: true }),

      clearError: () => set({ error: null }),
    }),
    {
      name: "insight-hub-auth",
      partialize: (state) => ({
        user:            state.user,
        token:           state.token,
        isAuthenticated: state.isAuthenticated,
        permissions:     state.permissions,
      }),
    },
  ),
);
