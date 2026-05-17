import ResetPasswordForm from "@/components/auth/ResetPasswordForm";
import { Metadata } from "next";
import { buildPageTitle, uiConfig } from "@/config/companyProfile";

export const metadata: Metadata = {
  title: buildPageTitle("Reset Password"),
  description: uiConfig.auth_description,
};

export default function ResetPasswordPage() {
  return <ResetPasswordForm />;
}
