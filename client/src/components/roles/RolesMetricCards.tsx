"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { MetricCard } from "../dashbaord/MetricCard";
import { ShieldCheck, Lock, Users } from "lucide-react";
import { useRBACMetricsQuery } from "@/hooks/queries/useRolesQuery";

export function RBACMetricCards() {
  const t = useTranslations("rbac.metrics");
  const { data } = useRBACMetricsQuery();

  const cards = [
    {
      icon:  <ShieldCheck className="h-6 w-6 text-brand-500" />,
      label: t("systemRoles"),
      value: data?.systemRoles ?? "—",
    },
    {
      icon:  <Lock className="h-6 w-6 text-theme-purple-500" />,
      label: t("permissionsDefined"),
      value: data ? `${data.permissionsDefined}` : "—",
    },
    {
      icon:  <Users className="h-6 w-6 text-success-500" />,
      label: t("activeUsers"),
      value: data?.activeUsers ?? "—",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
      {cards.map((card) => (
        <MetricCard
          key={card.label}
          icon={card.icon}
          label={card.label}
          value={card.value}
        />
      ))}
    </div>
  );
}
