import { Outfit } from "next/font/google";
import "@/app/globals.css";
import "flatpickr/dist/flatpickr.css";
import { SidebarProvider } from "@/context/SidebarContext";
import { ThemeProvider } from "@/context/ThemeContext";
import "react-toastify/dist/ReactToastify.css";
import { NextIntlClientProvider } from "next-intl";
import { routing } from "@/i18n/routing";
import { ThemedToastContainer } from "@/components/ui/toast-container";
import { ReactQueryProvider } from "@/providers/ReactQueryProvider";
import { AuthInitializer } from "@/components/auth/AuthInitializer";

const outfit = Outfit({ subsets: ["latin"] });

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  const activeLocale = routing.locales.includes(locale as "en" | "ko")
    ? locale
    : "en";

  const messages =
    activeLocale === "ko"
      ? (await import("../../../messages/ko.json")).default
      : (await import("../../../messages/en.json")).default;

  return (
    <div lang={activeLocale} className={`${outfit.className} dark:bg-gray-900`}>
      <NextIntlClientProvider locale={activeLocale} messages={messages}>
        <ReactQueryProvider>
          <ThemeProvider>
            <SidebarProvider>
              <ThemedToastContainer />
              {/* Validates the stored token on every page load, keeps user fresh */}
              <AuthInitializer />
              {children}
            </SidebarProvider>
          </ThemeProvider>
        </ReactQueryProvider>
      </NextIntlClientProvider>
    </div>
  );
}
