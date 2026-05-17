import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;

  if (!locale || !routing.locales.includes(locale as "en" | "ko")) {
    locale = routing.defaultLocale;
  }

  // ── WHY STATIC IMPORTS ────────────────────────────────────────────────────
  // A dynamic template literal like `import(`../../messages/${locale}.json`)`
  // cannot be statically analyzed by webpack/Next.js at build time.
  // This means webpack may NOT bundle ko.json into the build at all, so Korean
  // messages are never available at runtime and it silently falls back to English.
  //
  // Using a static lookup with explicit import() calls for each locale forces
  // webpack to include BOTH JSON files in the bundle, regardless of which one
  // is requested at runtime.
  // ─────────────────────────────────────────────────────────────────────────
  const messages =
    locale === "ko"
      ? (await import("../../messages/ko.json")).default
      : (await import("../../messages/en.json")).default;

  return {
    locale,
    messages,
  };
});