#!/usr/bin/env python3
"""
End-to-End Integration Test  (Prompt 05 Stage 3)

Validates the full pipeline:
  upload â†’ ingest (Celery) â†’ status poll â†’ progress â†’ category â†’ delete

Usage:
    python tests/integration_test.py
    python tests/integration_test.py --file tests/fixtures/test_sample.pdf
    python tests/integration_test.py --file E:/path/to/real.pdf --skip-delete
    python tests/integration_test.py --base-url http://localhost:8000/api --timeout 180

Exit codes:
    0  all tests passed
    1  one or more assertions failed
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

# â”€â”€â”€ defaults â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

DEFAULT_BASE_URL  = "http://localhost:8000/api"
DEFAULT_FIXTURE   = Path(__file__).parent / "fixtures" / "test_sample.pdf"
DEFAULT_TIMEOUT   = 120   # seconds to wait for Processing â†’ Completed
POLL_INTERVAL     = 3     # seconds between status polls


# â”€â”€â”€ result tracker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Results:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def section(self, title: str) -> None:
        print(f"\n{'â”€' * 64}")
        print(f"  {title}")
        print(f"{'â”€' * 64}")

    def ok(self, label: str) -> None:
        self.passed += 1
        print(f"  PASS  {label}")

    def fail(self, label: str, detail: str = "") -> None:
        self.failed += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")

    def summary(self) -> int:
        total = self.passed + self.failed
        print(f"\n{'=' * 64}")
        if self.failed == 0:
            print(f"  {self.passed}/{total} passed â€” ALL PASSED")
        else:
            print(f"  {self.passed}/{total} passed â€” {self.failed} FAILED")
        print(f"{'=' * 64}")
        return 1 if self.failed else 0


# â”€â”€â”€ assertion helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def check(r: Results, label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        r.ok(label)
    else:
        r.fail(label, detail)
    return condition


def check_status(r: Results, label: str, resp: httpx.Response, expected: int) -> bool:
    ok = resp.status_code == expected
    detail = f"HTTP {resp.status_code} body={resp.text[:300]}" if not ok else ""
    return check(r, label, ok, detail)


def safe_json(resp: httpx.Response) -> dict | list:
    """Parse response JSON safely â€” returns {} on non-JSON bodies (e.g. 500 tracebacks)."""
    try:
        return resp.json()
    except Exception:
        return {}


def check_field(
    r: Results,
    label: str,
    obj: dict,
    field: str,
    expected=None,
) -> bool:
    if field not in obj:
        r.fail(label, f"field '{field}' missing from {list(obj.keys())}")
        return False
    if expected is not None and obj[field] != expected:
        r.fail(label, f"'{field}' expected {expected!r}, got {obj[field]!r}")
        return False
    r.ok(label)
    return True


def assert_doc_shape(r: Results, doc: dict, prefix: str = "") -> None:
    """Assert that a dict matches the frontend Document shape."""
    for field in ("id", "filename", "type", "size", "sizeBytes", "source", "status", "uploadedAt"):
        check_field(r, f"{prefix}has '{field}'", doc, field)
    check(
        r,
        f"{prefix}status is Processing|Completed|Failed",
        doc.get("status") in ("Processing", "Completed", "Failed"),
        f"got {doc.get('status')!r}",
    )
    check(
        r,
        f"{prefix}sizeBytes is int > 0",
        isinstance(doc.get("sizeBytes"), int) and doc.get("sizeBytes", 0) > 0,
        f"got {doc.get('sizeBytes')!r}",
    )


# â”€â”€â”€ test sections â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_health(client: httpx.Client, r: Results) -> None:
    r.section("1. Health Check â€” GET /health")
    resp = client.get("/health")
    if not check_status(r, "GET /health â†’ 200", resp, 200):
        return
    body = resp.json()
    for svc in ("postgres", "redis", "minio", "qdrant"):
        status = body.get(svc, {}).get("status")
        check(r, f"{svc} status=ok", status == "ok", f"got {status!r}")


def test_upload_single(client: httpx.Client, r: Results, fixture: Path) -> str | None:
    r.section("2. Upload â€” single file  POST /documents/upload")
    with open(fixture, "rb") as fh:
        resp = client.post(
            "/documents/upload",
            files={"files": (fixture.name, fh, "application/pdf")},
            data={"category": "SOP"},
            timeout=60.0,
        )
    if not check_status(r, "POST /upload â†’ 200", resp, 200):
        return None

    body = resp.json()
    check(r, "response is a non-empty list", isinstance(body, list) and len(body) == 1,
          f"got type={type(body)} len={len(body) if isinstance(body, list) else 'n/a'}")
    if not isinstance(body, list) or not body:
        return None

    doc = body[0]
    assert_doc_shape(r, doc, prefix="  ")
    check(r, "  source=Upload",   doc.get("source") == "Upload")
    check(r, "  category=SOP",    doc.get("category") == "SOP")
    check(r, "  id is a string",  isinstance(doc.get("id"), str) and len(doc.get("id", "")) > 0)
    return doc.get("id")


def test_upload_multi(client: httpx.Client, r: Results, fixture: Path) -> list[str]:
    r.section("3. Upload â€” multi-file (2 copies)  POST /documents/upload")
    with open(fixture, "rb") as fh1, open(fixture, "rb") as fh2:
        resp = client.post(
            "/documents/upload",
            files=[
                ("files", (f"copy_a_{fixture.name}", fh1, "application/pdf")),
                ("files", (f"copy_b_{fixture.name}", fh2, "application/pdf")),
            ],
            data={"category": "Report"},
            timeout=60.0,
        )
    if not check_status(r, "POST /upload (2 files) â†’ 200", resp, 200):
        return []

    body = resp.json()
    check(r, "response has 2 items", isinstance(body, list) and len(body) == 2,
          f"got {len(body) if isinstance(body, list) else type(body)}")
    if not isinstance(body, list) or len(body) < 2:
        return [d.get("id") for d in (body or []) if d.get("id")]

    for i, doc in enumerate(body):
        assert_doc_shape(r, doc, prefix=f"  doc[{i}] ")
        check(r, f"  doc[{i}] category=Report", doc.get("category") == "Report")

    ids = [d.get("id") for d in body if d.get("id")]
    check(r, "both docs have distinct ids", len(set(ids)) == 2, f"ids={ids}")
    return ids


def test_list(client: httpx.Client, r: Results, known_ids: list[str]) -> None:
    r.section("4. Document List  GET /documents")

    # base list
    resp = client.get("/documents")
    if not check_status(r, "GET /documents â†’ 200", resp, 200):
        return
    body = resp.json()
    check(r, "response is a list", isinstance(body, list), str(type(body)))
    if isinstance(body, list) and body:
        assert_doc_shape(r, body[0], prefix="  list[0] ")

    # pagination
    resp_p = client.get("/documents", params={"page": 1, "limit": 2})
    check_status(r, "GET /documents?page=1&limit=2 â†’ 200", resp_p, 200)
    check(r, "  paginated result is â‰¤2 items",
          isinstance(resp_p.json(), list) and len(resp_p.json()) <= 2)

    # search â€” known miss
    resp_miss = client.get("/documents", params={"search": "zzz_no_match_xyz_integration"})
    check_status(r, "GET /documents?search=<no match> â†’ 200", resp_miss, 200)
    check(r, "  no-match search returns []", resp_miss.json() == [])

    # status filter: Failed should be accepted
    resp_failed = client.get("/documents", params={"status": "Failed"})
    check_status(r, "GET /documents?status=Failed â†’ 200", resp_failed, 200)
    check(r, "  failed-status response is a list", isinstance(resp_failed.json(), list))

    # invalid status â†’ 400
    resp_bad = client.get("/documents", params={"status": "bad_status_value"})
    check_status(r, "GET /documents?status=bad â†’ 400", resp_bad, 400)
    check(r, "  400 response has 'message'", "message" in safe_json(resp_bad))


def test_get_single(client: httpx.Client, r: Results, doc_id: str) -> None:
    r.section(f"5. Get Single Document  GET /documents/{{id}}")
    resp = client.get(f"/documents/{doc_id}")
    if not check_status(r, f"GET /documents/{doc_id[:8]}... â†’ 200", resp, 200):
        return
    doc = resp.json()
    check_field(r, "  id matches", doc, "id", expected=doc_id)
    assert_doc_shape(r, doc, prefix="  ")


def test_poll_until_completed(
    client: httpx.Client,
    r: Results,
    doc_id: str,
    timeout: int,
) -> bool:
    r.section(f"6. Status Polling  GET /documents/{{id}}/status  (timeout={timeout}s)")
    deadline = time.time() + timeout
    poll_count = 0
    last_status = None

    while time.time() < deadline:
        resp = client.get(f"/documents/{doc_id}/status")
        if not check_status(r, f"  poll {poll_count + 1}: GET /status â†’ 200", resp, 200):
            return False
        body = resp.json()
        last_status = body.get("status")
        poll_count += 1

        valid = last_status in ("Processing", "Completed", "Failed")
        check(r, f"  poll {poll_count}: status={last_status!r} is valid", valid,
              f"unexpected value {last_status!r}")

        if last_status == "Completed":
            r.ok(f"  reached Completed after {poll_count} poll(s)")
            check(r, "  response has 'id'",        body.get("id") == doc_id,   f"got {body.get('id')!r}")
            check(r, "  response has 'updatedAt'",  "updatedAt" in body)
            check(r, "  response has 'errorMessage'", "errorMessage" in body)
            return True

        if last_status == "Failed":
            r.fail("  ingestion reached Failed status", f"errorMessage={body.get('errorMessage')!r}")
            return False

        time.sleep(POLL_INTERVAL)

    r.fail(
        f"Timed out after {timeout}s â€” last status={last_status!r}",
        "Increase --timeout or check that the Celery worker is running.",
    )
    return False


def test_progress(client: httpx.Client, r: Results, doc_id: str) -> None:
    r.section(f"7. Progress History  GET /documents/{{id}}/progress")
    resp = client.get(f"/documents/{doc_id}/progress")
    if not check_status(r, f"GET /progress/{doc_id[:8]}... â†’ 200", resp, 200):
        return

    body = resp.json()
    check_field(r, "  has 'id'",      body, "id",      expected=doc_id)
    check_field(r, "  has 'status'",  body, "status")
    check_field(r, "  has 'current'", body, "current")
    check_field(r, "  has 'history'", body, "history")

    check(r, "  status is Processing|Completed|Failed",
          body.get("status") in ("Processing", "Completed", "Failed"),
          f"got {body.get('status')!r}")

    history = body.get("history", [])
    check(r, "  history is a list", isinstance(history, list))
    if history:
        for field in ("stage", "percent", "message", "createdAt"):
            check_field(r, f"  history[0] has '{field}'", history[0], field)
        check(r, "  history[0] percent is 0-100",
              isinstance(history[0].get("percent"), int)
              and 0 <= history[0].get("percent", -1) <= 100)

    current = body.get("current")
    if current is not None:
        check_field(r, "  current has 'stage'",   current, "stage")
        check_field(r, "  current has 'percent'", current, "percent")

    # limit param
    resp2 = client.get(f"/documents/{doc_id}/progress", params={"limit": 2})
    check_status(r, "  GET /progress?limit=2 â†’ 200", resp2, 200)
    check(r, "  limit=2 returns â‰¤2 history rows",
          len(resp2.json().get("history", [])) <= 2)


def test_category_single(client: httpx.Client, r: Results, doc_id: str) -> None:
    r.section(f"8. Category Update (single, immutable)  PATCH /documents/{{id}}/category")
    resp = client.patch(
        f"/documents/{doc_id}/category",
        json={"category": "Policy"},
    )
    check_status(r, "PATCH /category â†’ 409", resp, 409)
    check(r, "  409 has 'message'", "message" in safe_json(resp))


def test_category_bulk(client: httpx.Client, r: Results, doc_ids: list[str]) -> None:
    r.section("9. Category Update (bulk, immutable)  PATCH /documents/bulk/category")
    resp = client.patch(
        "/documents/bulk/category",
        json={"ids": doc_ids, "category": "Incident"},
    )
    check_status(r, f"PATCH /bulk/category ({len(doc_ids)} ids) â†’ 409", resp, 409)
    check(r, "  409 has 'message'", "message" in safe_json(resp))

    # empty ids â†’ 400
    resp_bad = client.patch("/documents/bulk/category", json={"ids": [], "category": "SOP"})
    check_status(r, "  empty ids â†’ 400", resp_bad, 400)
    check(r, "  400 has 'message'", "message" in safe_json(resp_bad))


def test_delete_bulk(
    client: httpx.Client,
    r: Results,
    doc_ids: list[str],
    skip_delete: bool,
) -> None:
    r.section(f"10. Bulk Delete  DELETE /documents/bulk  ({len(doc_ids)} docs)")
    if skip_delete:
        r.ok("skipped via --skip-delete (docs remain in DB for manual inspection)")
        return

    resp = client.request("DELETE", "/documents/bulk", json={"ids": doc_ids})
    if not check_status(r, f"DELETE /bulk ({len(doc_ids)} ids) â†’ 200", resp, 200):
        return
    body = resp.json()
    check(r, f"  deleted={len(doc_ids)}", body.get("deleted") == len(doc_ids),
          f"got {body.get('deleted')!r}")
    check(r, "  warnings is a list", isinstance(body.get("warnings"), list))

    # each deleted doc must now 404
    for doc_id in doc_ids:
        resp2 = client.get(f"/documents/{doc_id}/status")
        check_status(r, f"  GET /status after delete â†’ 404 ({doc_id[:8]}...)", resp2, 404)
        check(r, f"  404 has 'message' ({doc_id[:8]}...)", "message" in safe_json(resp2))

    # empty ids â†’ 400
    resp_bad = client.request("DELETE", "/documents/bulk", json={"ids": []})
    check_status(r, "  empty ids â†’ 400", resp_bad, 400)
    check(r, "  400 has 'message'", "message" in safe_json(resp_bad))

    # duplicate ids â†’ treated as one, no crash
    if doc_ids:
        dup = [doc_ids[0], doc_ids[0]]
        resp_dup = client.request("DELETE", "/documents/bulk", json={"ids": dup})
        check(r, "  duplicate ids â†’ 200 or 404 (no 500)",
              resp_dup.status_code in (200, 404),
              f"got {resp_dup.status_code}")


def test_not_found_handling(client: httpx.Client, r: Results) -> None:
    r.section("11. 404 Handling â€” non-existent doc_id")
    fake = "00000000-0000-0000-0000-000000000000"
    endpoints = [
        f"/documents/{fake}",
        f"/documents/{fake}/status",
        f"/documents/{fake}/progress",
    ]
    for path in endpoints:
        resp = client.get(path)
        check_status(r, f"GET {path} â†’ 404", resp, 404)
        check(r, f"  {path} body has 'message'", "message" in safe_json(resp))

    # DELETE non-existent â†’ warnings (not 500)
    resp_del = client.request("DELETE", "/documents/bulk", json={"ids": [fake]})
    check_status(r, f"DELETE /bulk with unknown id â†’ 200", resp_del, 200)
    check(r, "  deleted=0, warning captured",
          safe_json(resp_del).get("deleted") == 0
          and isinstance(safe_json(resp_del).get("warnings"), list)
          and len(safe_json(resp_del).get("warnings", [])) > 0)


# â”€â”€â”€ main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end integration test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python tests/integration_test.py
  python tests/integration_test.py --file tests/fixtures/test_sample.pdf
  python tests/integration_test.py --file E:/path/to/real.pdf --skip-delete
  python tests/integration_test.py --base-url http://localhost:8000/api --timeout 180
""",
    )
    parser.add_argument(
        "--file", type=Path, default=DEFAULT_FIXTURE,
        help=f"PDF to upload (default: {DEFAULT_FIXTURE})",
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help=f"Seconds to wait for ingestion to complete (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--skip-delete", action="store_true",
        help="Skip delete step â€” leaves test docs in DB for manual inspection",
    )
    args = parser.parse_args()

    # pre-flight: fixture must exist
    if not args.file.exists():
        print(f"\nERROR: fixture not found: {args.file}")
        print("  Generate it first:")
        print("    python scripts/generate_test_pdf.py")
        sys.exit(1)

    print("\nIntegration Test")
    print(f"  base_url  : {args.base_url}")
    print(f"  fixture   : {args.file}  ({args.file.stat().st_size:,} bytes)")
    print(f"  timeout   : {args.timeout}s")
    print(f"  delete    : {'SKIPPED (--skip-delete)' if args.skip_delete else 'enabled'}")

    r = Results()
    client = httpx.Client(base_url=args.base_url, timeout=30.0)
    all_ids: list[str] = []

    try:
        # â”€â”€ 1. infrastructure health â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        test_health(client, r)

        # â”€â”€ 2-3. upload â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        single_id = test_upload_single(client, r, args.file)
        if single_id:
            all_ids.append(single_id)

        multi_ids = test_upload_multi(client, r, args.file)
        all_ids.extend(multi_ids)

        # â”€â”€ 4-5. list + get single â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        test_list(client, r, all_ids)
        if single_id:
            test_get_single(client, r, single_id)

        # â”€â”€ 6. poll until Completed (single upload) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        ingestion_ok = False
        if single_id:
            ingestion_ok = test_poll_until_completed(client, r, single_id, args.timeout)

        # â”€â”€ 7. progress (only meaningful once Completed) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if single_id:
            test_progress(client, r, single_id)

        # â”€â”€ 8-9. category mutations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if single_id:
            test_category_single(client, r, single_id)
        if all_ids:
            test_category_bulk(client, r, all_ids)

        # â”€â”€ 10. delete â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if all_ids:
            test_delete_bulk(client, r, all_ids, args.skip_delete)

        # â”€â”€ 11. 404 / error handling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        test_not_found_handling(client, r)

    except httpx.ConnectError:
        print(f"\nFATAL: cannot connect to {args.base_url}")
        print("  Start the server first:")
        print("    python -m uvicorn app.main:app --reload --port 8000")
        sys.exit(1)

    finally:
        client.close()

    sys.exit(r.summary())


if __name__ == "__main__":
    main()


