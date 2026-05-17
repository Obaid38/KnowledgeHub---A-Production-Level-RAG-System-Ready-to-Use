import rawCompanyProfile from "../../../config/company_profile.json";

type RawProfile = typeof rawCompanyProfile;

export type CompanyProfile = RawProfile;

function requireNonEmptyString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${path} must be a non-empty string`);
  }
  return value.trim();
}

function readStringList(value: unknown, path: string): string[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) {
    throw new Error(`${path} must be an array`);
  }
  return value
    .map((item) => String(item ?? "").trim())
    .filter(Boolean);
}

function validateLogoPath(value: string, path: string): string {
  if (!value.startsWith("/")) {
    throw new Error(`${path} must start with '/'`);
  }
  return value;
}

function validateProfile(raw: RawProfile): CompanyProfile {
  const brand = raw.brand ?? {};
  const company = raw.company ?? {};
  const domain = raw.domain ?? {};
  const qa = raw.qa ?? {};
  const contact = raw.contact ?? {};
  const ui = raw.ui ?? {};

  return {
    brand: {
      app_name: requireNonEmptyString(brand.app_name, "brand.app_name"),
      app_tagline: requireNonEmptyString(brand.app_tagline, "brand.app_tagline"),
      product_description: requireNonEmptyString(
        brand.product_description,
        "brand.product_description",
      ),
      logo_light_path: validateLogoPath(
        requireNonEmptyString(brand.logo_light_path, "brand.logo_light_path"),
        "brand.logo_light_path",
      ),
      logo_dark_path: validateLogoPath(
        requireNonEmptyString(brand.logo_dark_path, "brand.logo_dark_path"),
        "brand.logo_dark_path",
      ),
      favicon_path: validateLogoPath(
        requireNonEmptyString(brand.favicon_path, "brand.favicon_path"),
        "brand.favicon_path",
      ),
    },
    company: {
      legal_name: requireNonEmptyString(company.legal_name, "company.legal_name"),
      short_name: requireNonEmptyString(company.short_name, "company.short_name"),
      aliases: readStringList(company.aliases, "company.aliases"),
      knowledge_base_label: requireNonEmptyString(
        company.knowledge_base_label,
        "company.knowledge_base_label",
      ),
      domain_summary: requireNonEmptyString(
        company.domain_summary,
        "company.domain_summary",
      ),
    },
    domain: {
      teams: readStringList(domain.teams, "domain.teams"),
      systems: readStringList(domain.systems, "domain.systems"),
      customers: readStringList(domain.customers, "domain.customers"),
      carriers: readStringList(domain.carriers, "domain.carriers"),
      warehouse_partners: readStringList(
        domain.warehouse_partners,
        "domain.warehouse_partners",
      ),
      abbreviations: readStringList(domain.abbreviations, "domain.abbreviations"),
      strong_in_terms: readStringList(domain.strong_in_terms, "domain.strong_in_terms"),
      generic_domain_terms: readStringList(
        domain.generic_domain_terms,
        "domain.generic_domain_terms",
      ),
      faithfulness_entities: readStringList(
        domain.faithfulness_entities,
        "domain.faithfulness_entities",
      ),
      cleaner_known_customers: readStringList(
        domain.cleaner_known_customers,
        "domain.cleaner_known_customers",
      ),
      cleaner_known_carriers: readStringList(
        domain.cleaner_known_carriers,
        "domain.cleaner_known_carriers",
      ),
    },
    qa: {
      suggested_prompts: readStringList(qa.suggested_prompts, "qa.suggested_prompts"),
      no_result_message: requireNonEmptyString(
        qa.no_result_message,
        "qa.no_result_message",
      ),
    },
    contact: {
      support_email: requireNonEmptyString(
        contact.support_email,
        "contact.support_email",
      ),
      no_reply_email: requireNonEmptyString(
        contact.no_reply_email,
        "contact.no_reply_email",
      ),
      seed_superadmin_email: requireNonEmptyString(
        contact.seed_superadmin_email,
        "contact.seed_superadmin_email",
      ),
    },
    ui: {
      page_title_suffix: requireNonEmptyString(
        ui.page_title_suffix,
        "ui.page_title_suffix",
      ),
      auth_description: requireNonEmptyString(
        ui.auth_description,
        "ui.auth_description",
      ),
    },
  };
}

export const companyProfile = validateProfile(rawCompanyProfile);

export const brandConfig = companyProfile.brand;
export const companyConfig = companyProfile.company;
export const qaConfig = companyProfile.qa;
export const uiConfig = companyProfile.ui;

export function buildPageTitle(title: string): string {
  return `${title} | ${uiConfig.page_title_suffix}`;
}
