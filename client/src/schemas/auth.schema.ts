// src/schemas/auth.schema.ts
import { z } from "zod";

// ─── Sign In ──────────────────────────────────────────────────────────────────
export const signInSchema = z.object({
  email: z
    .string()
    .min(1, "Email is required")
    .email("Enter a valid email address"),
  password: z
    .string()
    .min(1, "Password is required")
    .min(6, "Password must be at least 6 characters"),
});

export type SignInFormValues = z.infer<typeof signInSchema>;

// ─── Sign Up ──────────────────────────────────────────────────────────────────
export const signUpSchema = z
  .object({
    firstName: z
      .string()
      .min(1, "First name is required")
      .max(50, "First name is too long"),
    lastName: z
      .string()
      .min(1, "Last name is required")
      .max(50, "Last name is too long"),
    email: z
      .string()
      .min(1, "Email is required")
      .email("Enter a valid email address"),
    password: z
      .string()
      .min(1, "Password is required")
      .min(8, "Password must be at least 8 characters")
      .regex(/[A-Z]/, "Must contain at least one uppercase letter")
      .regex(/[0-9]/, "Must contain at least one number"),
    confirmPassword: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

export type SignUpFormValues = z.infer<typeof signUpSchema>;

// ─── MFA (TOTP) ───────────────────────────────────────────────────────────────
export const mfaSchema = z.object({
  code: z
    .string()
    .length(6, "Code must be exactly 6 digits")
    .regex(/^\d+$/, "Code must contain digits only"),
});

export type MfaFormValues = z.infer<typeof mfaSchema>;

// ─── MFA Recovery ─────────────────────────────────────────────────────────────
export const mfaRecoverySchema = z.object({
  recoveryCode: z
    .string()
    .min(1, "Recovery code is required")
    .min(8, "Enter a valid recovery code"),
});

export type MfaRecoveryFormValues = z.infer<typeof mfaRecoverySchema>;

// ─── Forgot Password ──────────────────────────────────────────────────────────
export const forgotPasswordSchema = z.object({
  email: z
    .string()
    .min(1, "Email is required")
    .email("Enter a valid email address"),
});

export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;