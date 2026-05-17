import MfaForm from "@/components/auth/MfaForm";
import { Metadata } from "next";
import { buildPageTitle, uiConfig } from "@/config/companyProfile";

export const metadata: Metadata = {
  title: buildPageTitle("Two-Factor Authentication"),
  description: uiConfig.auth_description,
};

export default function MfaPage() {
  return <MfaForm />;
}
