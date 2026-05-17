"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "next/navigation";
import { useTransition } from "react";

const LOCALES = ["en", "ko"];

export default function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const rawPathname = usePathname(); // e.g. "/en/dashboard" or "/ko/dashboard"
  const [isPending, startTransition] = useTransition();

  function switchLocale(next: string) {
    if (next === locale) return;
    let cleanPath = "/";
    for (const loc of LOCALES) {
      if (rawPathname.startsWith(`/${loc}/`)) {
        cleanPath = rawPathname.slice(loc.length + 1); // "/dashboard"
        break;
      }
      if (rawPathname === `/${loc}`) {
        cleanPath = "/";
        break;
      }
    }

    // Build new URL — always include the new locale prefix
    const newPath =
      cleanPath === "/" ? `/${next}` : `/${next}${cleanPath}`;

    startTransition(() => {
      router.push(newPath);
      router.refresh();
    });
  }

  return (
    <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-800 dark:bg-gray-900">
      <button
        onClick={() => switchLocale("en")}
        disabled={isPending}
        aria-label="Switch to English"
        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
          locale === "en"
            ? "bg-brand-500 text-white"
            : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        }`}
      >
        <span>🇺🇸</span>
        <span>EN</span>
      </button>

      <button
        onClick={() => switchLocale("ko")}
        disabled={isPending}
        aria-label="Switch to Korean"
        className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
          locale === "ko"
            ? "bg-brand-500 text-white"
            : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        }`}
      >
        <span>🇰🇷</span>
        <span>한국어</span>
      </button>
    </div>
  );
}