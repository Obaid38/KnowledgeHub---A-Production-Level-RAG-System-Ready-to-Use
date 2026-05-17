import ForgotPasswordForm from "@/components/auth/ForgotPasswordFrom";
import { Metadata } from "next";
import { buildPageTitle, uiConfig } from "@/config/companyProfile";

export const metadata: Metadata = {
  title: buildPageTitle("Forgot Password"),
  description: uiConfig.auth_description,
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
