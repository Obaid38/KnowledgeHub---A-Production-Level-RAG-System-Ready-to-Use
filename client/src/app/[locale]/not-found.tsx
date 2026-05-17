import GridShape from "@/components/common/GridShape";
import Image from "next/image";
import Link from "next/link";
import { getTranslations, getLocale } from "next-intl/server";
import { cookies } from "next/headers";
import { uiConfig } from "@/config/companyProfile";

export default async function NotFound() {
  const t = await getTranslations("errors.notFound");
  const locale = await getLocale();
  const cookieStore = await cookies();
  const role = cookieStore.get("user-role")?.value?.toLowerCase();
  const isAdmin = role === "admin" || role === "superadmin";
  const homeHref = isAdmin ? `/${locale}` : `/${locale}/qa`;

  return (
    <div className="relative flex flex-col items-center justify-center min-h-screen p-6 overflow-hidden z-1">
      <GridShape />
      <div className="mx-auto w-full max-w-[242px] text-center sm:max-w-[472px]">
        <h1 className="mb-8 font-bold text-gray-800 text-title-md dark:text-white/90 xl:text-title-2xl">
          {t("heading")}
        </h1>
        <Image src="/images/error/404.svg"      alt="404" className="dark:hidden"       width={472} height={152} />
        <Image src="/images/error/404-dark.svg" alt="404" className="hidden dark:block" width={472} height={152} />
        <p className="mt-10 mb-6 text-base text-gray-700 dark:text-gray-400 sm:text-lg">
          {t("message")}
        </p>
        <Link
          href={homeHref}
          className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white px-5 py-3.5 text-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/[0.03] dark:hover:text-gray-200"
        >
          {t("backHome")}
        </Link>
      </div>
      <p className="absolute text-sm text-center text-gray-500 -translate-x-1/2 bottom-6 left-1/2 dark:text-gray-400">
        &copy; {new Date().getFullYear()} - {uiConfig.page_title_suffix}
      </p>
    </div>
  );
}
