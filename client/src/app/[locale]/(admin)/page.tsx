import React from "react";
import type { Metadata } from "next";
import { getTranslations, getLocale } from "next-intl/server";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { DashboardMetrics } from "@/components/dashbaord/DashboardMetrics";
import { QueryVolumeChart } from "@/components/dashbaord/QueryVolumeChart";
import { ActivityFeed } from "@/components/dashbaord/ActivityFeed";
import { RecentQueries } from "@/components/dashbaord/RecentQueries";
import { buildPageTitle } from "@/config/companyProfile";

// ─── Metadata ─────────────────────────────────────────────────────────────────

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("dashboard");
  return {
    title: buildPageTitle(t("title")),
    description: t("subtitle"),
  };
}

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const role = cookieStore.get("user-role")?.value?.toLowerCase();
  const isAdmin = role === "admin" || role === "superadmin";

  if (!isAdmin) {
    const locale = await getLocale();
    redirect(`/${locale}/qa`);
  }

  const t = await getTranslations("dashboard");

  return (
    <div className="space-y-6">
      <div>
        <h1>{t("title")}</h1>
        <p>{t("subtitle")}</p>
      </div>
      <DashboardMetrics />
      <div className="grid grid-cols-12 gap-4 md:gap-6">
        <div className="col-span-12 xl:col-span-8">
          <QueryVolumeChart />
        </div>
        <div className="col-span-12 xl:col-span-4">
          <ActivityFeed />
        </div>
      </div>
      <RecentQueries />
    </div>
  );
}
