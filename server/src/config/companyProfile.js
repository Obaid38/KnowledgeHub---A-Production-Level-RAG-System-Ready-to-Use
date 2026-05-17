const fs = require("fs");
const path = require("path");

const PROFILE_PATH = path.resolve(__dirname, "../../../config/company_profile.json");

let cachedProfile = null;

function requireNonEmptyString(section, key, sectionName) {
  const value = section?.[key];
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${sectionName}.${key} must be a non-empty string`);
  }
  return value.trim();
}

function readStringList(section, key) {
  const value = section?.[key];
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) {
    throw new Error(`${key} must be an array`);
  }
  return value
    .map((item) => String(item ?? "").trim())
    .filter(Boolean);
}

function validateLogoPath(value, key) {
  if (!value.startsWith("/")) {
    throw new Error(`brand.${key} must start with '/'`);
  }
  return value;
}

function loadCompanyProfile() {
  if (cachedProfile) return cachedProfile;

  if (!fs.existsSync(PROFILE_PATH)) {
    throw new Error(`company_profile.json not found: ${PROFILE_PATH}`);
  }

  const raw = JSON.parse(fs.readFileSync(PROFILE_PATH, "utf8"));
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("company profile must be a JSON object");
  }

  const brand = raw.brand;
  const company = raw.company;
  const domain = raw.domain;
  const qa = raw.qa;
  const contact = raw.contact;
  const ui = raw.ui;

  if (!brand || typeof brand !== "object") throw new Error("brand must be an object");
  if (!company || typeof company !== "object") throw new Error("company must be an object");
  if (!domain || typeof domain !== "object") throw new Error("domain must be an object");
  if (!qa || typeof qa !== "object") throw new Error("qa must be an object");
  if (!contact || typeof contact !== "object") throw new Error("contact must be an object");
  if (!ui || typeof ui !== "object") throw new Error("ui must be an object");

  cachedProfile = {
    brand: {
      appName: requireNonEmptyString(brand, "app_name", "brand"),
      appTagline: requireNonEmptyString(brand, "app_tagline", "brand"),
      productDescription: requireNonEmptyString(brand, "product_description", "brand"),
      logoLightPath: validateLogoPath(
        requireNonEmptyString(brand, "logo_light_path", "brand"),
        "logo_light_path",
      ),
      logoDarkPath: validateLogoPath(
        requireNonEmptyString(brand, "logo_dark_path", "brand"),
        "logo_dark_path",
      ),
      faviconPath: validateLogoPath(
        requireNonEmptyString(brand, "favicon_path", "brand"),
        "favicon_path",
      ),
    },
    company: {
      legalName: requireNonEmptyString(company, "legal_name", "company"),
      shortName: requireNonEmptyString(company, "short_name", "company"),
      aliases: readStringList(company, "aliases"),
      knowledgeBaseLabel: requireNonEmptyString(
        company,
        "knowledge_base_label",
        "company",
      ),
      domainSummary: requireNonEmptyString(company, "domain_summary", "company"),
    },
    domain: {
      teams: readStringList(domain, "teams"),
      systems: readStringList(domain, "systems"),
      customers: readStringList(domain, "customers"),
      carriers: readStringList(domain, "carriers"),
      warehousePartners: readStringList(domain, "warehouse_partners"),
      abbreviations: readStringList(domain, "abbreviations"),
      strongInTerms: readStringList(domain, "strong_in_terms"),
      genericDomainTerms: readStringList(domain, "generic_domain_terms"),
      faithfulnessEntities: readStringList(domain, "faithfulness_entities"),
      cleanerKnownCustomers: readStringList(domain, "cleaner_known_customers"),
      cleanerKnownCarriers: readStringList(domain, "cleaner_known_carriers"),
    },
    qa: {
      suggestedPrompts: readStringList(qa, "suggested_prompts"),
      noResultMessage: requireNonEmptyString(qa, "no_result_message", "qa"),
    },
    contact: {
      supportEmail: requireNonEmptyString(contact, "support_email", "contact"),
      noReplyEmail: requireNonEmptyString(contact, "no_reply_email", "contact"),
      seedSuperadminEmail: requireNonEmptyString(
        contact,
        "seed_superadmin_email",
        "contact",
      ),
    },
    ui: {
      pageTitleSuffix: requireNonEmptyString(ui, "page_title_suffix", "ui"),
      authDescription: requireNonEmptyString(ui, "auth_description", "ui"),
    },
  };

  return cachedProfile;
}

module.exports = {
  loadCompanyProfile,
  PROFILE_PATH,
};
