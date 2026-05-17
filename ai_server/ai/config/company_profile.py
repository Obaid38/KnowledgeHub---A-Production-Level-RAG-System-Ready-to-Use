import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class BrandConfig:
    app_name: str
    app_tagline: str
    product_description: str
    logo_light_path: str
    logo_dark_path: str
    favicon_path: str


@dataclass(frozen=True)
class CompanyConfig:
    legal_name: str
    short_name: str
    aliases: list[str] = field(default_factory=list)
    knowledge_base_label: str = ""
    domain_summary: str = ""


@dataclass(frozen=True)
class DomainConfig:
    teams: list[str] = field(default_factory=list)
    systems: list[str] = field(default_factory=list)
    customers: list[str] = field(default_factory=list)
    carriers: list[str] = field(default_factory=list)
    warehouse_partners: list[str] = field(default_factory=list)
    abbreviations: list[str] = field(default_factory=list)
    strong_in_terms: list[str] = field(default_factory=list)
    generic_domain_terms: list[str] = field(default_factory=list)
    faithfulness_entities: list[str] = field(default_factory=list)
    cleaner_known_customers: list[str] = field(default_factory=list)
    cleaner_known_carriers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QAConfig:
    suggested_prompts: list[str] = field(default_factory=list)
    no_result_message: str = ""


@dataclass(frozen=True)
class ContactConfig:
    support_email: str
    no_reply_email: str
    seed_superadmin_email: str


@dataclass(frozen=True)
class UIConfig:
    page_title_suffix: str
    auth_description: str


@dataclass(frozen=True)
class CompanyProfile:
    brand: BrandConfig
    company: CompanyConfig
    domain: DomainConfig
    qa: QAConfig
    contact: ContactConfig
    ui: UIConfig


_PROFILE_PATH = Path(__file__).resolve().parents[3] / "config" / "company_profile.json"


def _require_non_empty_string(section: dict, key: str, section_name: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{section_name}.{key} must be a non-empty string")
    return value.strip()


def _read_string_list(section: dict, key: str) -> list[str]:
    value = section.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    cleaned: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _read_section(raw: dict, key: str) -> dict:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _validate_logo_path(path_value: str, key: str) -> str:
    if not path_value.startswith("/"):
        raise ValueError(f"brand.{key} must start with '/' for frontend assets")
    return path_value


def load_company_profile_from_path(path: Path) -> CompanyProfile:
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if not isinstance(raw, dict):
        raise ValueError("company profile must be a JSON object")

    brand_raw = _read_section(raw, "brand")
    company_raw = _read_section(raw, "company")
    domain_raw = _read_section(raw, "domain")
    qa_raw = _read_section(raw, "qa")
    contact_raw = _read_section(raw, "contact")
    ui_raw = _read_section(raw, "ui")

    brand = BrandConfig(
        app_name=_require_non_empty_string(brand_raw, "app_name", "brand"),
        app_tagline=_require_non_empty_string(brand_raw, "app_tagline", "brand"),
        product_description=_require_non_empty_string(brand_raw, "product_description", "brand"),
        logo_light_path=_validate_logo_path(
            _require_non_empty_string(brand_raw, "logo_light_path", "brand"),
            "logo_light_path",
        ),
        logo_dark_path=_validate_logo_path(
            _require_non_empty_string(brand_raw, "logo_dark_path", "brand"),
            "logo_dark_path",
        ),
        favicon_path=_validate_logo_path(
            _require_non_empty_string(brand_raw, "favicon_path", "brand"),
            "favicon_path",
        ),
    )
    company = CompanyConfig(
        legal_name=_require_non_empty_string(company_raw, "legal_name", "company"),
        short_name=_require_non_empty_string(company_raw, "short_name", "company"),
        aliases=_read_string_list(company_raw, "aliases"),
        knowledge_base_label=_require_non_empty_string(
            company_raw,
            "knowledge_base_label",
            "company",
        ),
        domain_summary=_require_non_empty_string(company_raw, "domain_summary", "company"),
    )
    domain = DomainConfig(
        teams=_read_string_list(domain_raw, "teams"),
        systems=_read_string_list(domain_raw, "systems"),
        customers=_read_string_list(domain_raw, "customers"),
        carriers=_read_string_list(domain_raw, "carriers"),
        warehouse_partners=_read_string_list(domain_raw, "warehouse_partners"),
        abbreviations=_read_string_list(domain_raw, "abbreviations"),
        strong_in_terms=_read_string_list(domain_raw, "strong_in_terms"),
        generic_domain_terms=_read_string_list(domain_raw, "generic_domain_terms"),
        faithfulness_entities=_read_string_list(domain_raw, "faithfulness_entities"),
        cleaner_known_customers=_read_string_list(domain_raw, "cleaner_known_customers"),
        cleaner_known_carriers=_read_string_list(domain_raw, "cleaner_known_carriers"),
    )
    qa = QAConfig(
        suggested_prompts=_read_string_list(qa_raw, "suggested_prompts"),
        no_result_message=_require_non_empty_string(qa_raw, "no_result_message", "qa"),
    )
    contact = ContactConfig(
        support_email=_require_non_empty_string(contact_raw, "support_email", "contact"),
        no_reply_email=_require_non_empty_string(contact_raw, "no_reply_email", "contact"),
        seed_superadmin_email=_require_non_empty_string(
            contact_raw,
            "seed_superadmin_email",
            "contact",
        ),
    )
    ui = UIConfig(
        page_title_suffix=_require_non_empty_string(ui_raw, "page_title_suffix", "ui"),
        auth_description=_require_non_empty_string(ui_raw, "auth_description", "ui"),
    )

    return CompanyProfile(
        brand=brand,
        company=company,
        domain=domain,
        qa=qa,
        contact=contact,
        ui=ui,
    )


@lru_cache(maxsize=1)
def load_company_profile() -> CompanyProfile:
    if not _PROFILE_PATH.exists():
        raise FileNotFoundError(f"company_profile.json not found: {_PROFILE_PATH}")
    return load_company_profile_from_path(_PROFILE_PATH)
