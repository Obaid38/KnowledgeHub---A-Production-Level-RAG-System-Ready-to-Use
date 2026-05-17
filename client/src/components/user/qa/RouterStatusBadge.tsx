"use client";

import React from "react";
import { useTranslations } from "next-intl";
import Badge from "@/components/ui/badge/Badge";
import { QAMode } from "@/types/qa.types";
import { ROUTER_STATUSES } from "@/constants/qa.constants";

interface RouterStatusBadgesProps {
  mode: QAMode;
}

export function RouterStatusBadges({ mode }: RouterStatusBadgesProps) {
  const t = useTranslations("qa.router");

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {ROUTER_STATUSES.filter((s) => s.active).map((status) => {
        const color = status.mode === "rag" ? "primary" : "success" as const;
        const dotClass = status.mode === "rag" ? "bg-brand-500" : "bg-success-500";

        return (
          <Badge
            key={status.mode}
            variant="light"
            size="sm"
            color={color}
            startIcon={
              <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
            }
          >
            {t(status.label as any)}
          </Badge>
        );
      })}
    </div>
  );
}