#!/usr/bin/env python3
"""Unit tests for the shared company profile loader."""
import json
import sys
import tempfile
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from ai.config.company_profile import load_company_profile, load_company_profile_from_path


def test_company_profile_loads_generic_defaults() -> None:
    profile = load_company_profile()
    assert profile.brand.app_name == "Knowledge Hub"
    assert profile.company.legal_name == "Example Operations Inc."
    assert "MPG" not in json.dumps(profile.__dict__, default=lambda o: o.__dict__)


def test_company_profile_rejects_invalid_logo_path() -> None:
    bad_profile = {
        "brand": {
            "app_name": "Test",
            "app_tagline": "Tagline",
            "product_description": "Description",
            "logo_light_path": "images/logo.svg",
            "logo_dark_path": "/images/logo-dark.svg",
            "favicon_path": "/favicon.ico",
        },
        "company": {
            "legal_name": "Test Co",
            "short_name": "Test",
            "aliases": [],
            "knowledge_base_label": "knowledge base",
            "domain_summary": "Summary",
        },
        "domain": {},
        "qa": {
            "suggested_prompts": [],
            "no_result_message": "No result",
        },
        "contact": {
            "support_email": "support@example.test",
            "no_reply_email": "no-reply@example.test",
            "seed_superadmin_email": "superadmin@example.test",
        },
        "ui": {
            "page_title_suffix": "Test",
            "auth_description": "Auth description",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(bad_profile, handle)
        tmp_path = Path(handle.name)

    try:
        raised = False
        try:
            load_company_profile_from_path(tmp_path)
        except ValueError as exc:
            raised = True
            assert "logo_light_path" in str(exc)
        assert raised, "Expected invalid logo path to raise ValueError"
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    tests = [
        test_company_profile_loads_generic_defaults,
        test_company_profile_rejects_invalid_logo_path,
    ]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  PASS  {test_fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test_fn.__name__}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
