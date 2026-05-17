import SignUpForm from "@/components/auth/SignUpForm";
import { Metadata } from "next";
import { buildPageTitle, uiConfig } from "@/config/companyProfile";

export const metadata: Metadata = {
  title: buildPageTitle("Create Account"),
  description: uiConfig.auth_description,
};

export default function SignUpPage() {
  return <SignUpForm />;
}
