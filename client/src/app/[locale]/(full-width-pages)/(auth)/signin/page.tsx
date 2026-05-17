import SignInForm from "@/components/auth/SignInForm";
import { Metadata } from "next";
import { buildPageTitle, uiConfig } from "@/config/companyProfile";

export const metadata: Metadata = {
  title: buildPageTitle("Log In"),
  description: uiConfig.auth_description,
};

export default function SignInPage() {
  return <SignInForm />;
}
