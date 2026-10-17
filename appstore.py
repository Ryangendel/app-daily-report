"""Fetch daily iOS downloads from the App Store Connect Sales Reports API.

Flow: build a short-lived ES256 JWT -> GET /v1/salesReports (gzipped TSV)
-> sum the `Units` column for first-time-install product types.

Credentials needed (see README):
  - Issuer ID, Key ID, .p8 private key  (Users and Access -> Integrations)
  - Vendor Number                       (Payments and Financial Reports)
  - API key role: Admin, Finance, or Sales
"""

import csv
import gzip
import io
import time

import jwt
import requests

SALES_REPORTS_URL = "https://api.appstoreconnect.apple.com/v1/salesReports"

# Product Type Identifiers that count as genuine first-time downloads.
# (Excludes updates 7*, re-downloads 3*, and in-app purchases IA*.)
FIRST_TIME_INSTALL_TYPES = {"1", "1F", "1T", "F1", "1-B", "F1-B", "1E", "1EP", "1EU"}


def _make_token(issuer_id, key_id, private_key, lifetime=1000):
    """Build an App Store Connect JWT (ES256). Lifetime must be <= 20 min."""
    now = int(time.time())
    payload = {
        "iss": issuer_id,
        "iat": now,
        "exp": now + lifetime,
        "aud": "appstoreconnect-v1",
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": key_id})


def get_downloads(issuer_id, key_id, private_key, vendor_number, report_date,
                  version="1_1", timeout=60):
    """Return daily first-time iOS downloads for `report_date` (YYYY-MM-DD).

    Returns an int, or None if Apple hasn't finalized that day's report yet.
    A report with no data (NO_DATA) is treated as 0 downloads.
    """
    token = _make_token(issuer_id, key_id, private_key)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/a-gzip"}
    params = {
        "filter[frequency]": "DAILY",
        "filter[reportType]": "SALES",
        "filter[reportSubType]": "SUMMARY",
        "filter[vendorNumber]": vendor_number,
        "filter[reportDate]": report_date,
        "filter[version]": version,
    }

    resp = requests.get(SALES_REPORTS_URL, headers=headers, params=params, timeout=timeout)

    if resp.status_code == 200:
        return _sum_units(resp.content)

    # 404 can mean "no sales that day" (= 0) or "report not ready yet" (= None).
    if resp.status_code == 404:
        code = _error_code(resp)
        if code == "NO_DATA":
            return 0
        return None  # REPORT_NOT_AVAILABLE_YET or similar -> not ready

    # If the required report version changed, Apple returns the valid one.
    if resp.status_code in (400, 409):
        valid = _valid_version_from_error(resp)
        if valid and valid != version:
            return get_downloads(issuer_id, key_id, private_key, vendor_number,
                                 report_date, version=valid, timeout=timeout)

    resp.raise_for_status()
    return None


def _sum_units(gz_bytes):
    """Decompress the gzipped TSV and sum first-time-install Units."""
    raw = gzip.decompress(gz_bytes).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw), delimiter="\t")
    total = 0
    for row in reader:
        ptype = (row.get("Product Type Identifier") or "").strip()
        if ptype in FIRST_TIME_INSTALL_TYPES:
            try:
                total += int(float(row.get("Units", 0) or 0))
            except ValueError:
                continue
    return total


def _error_code(resp):
    try:
        return resp.json().get("errors", [{}])[0].get("code", "")
    except Exception:
        return ""


def _valid_version_from_error(resp):
    """Pull an accepted report version out of an error message, if present."""
    try:
        detail = resp.json().get("errors", [{}])[0].get("detail", "")
    except Exception:
        return None
    for token in detail.replace(",", " ").split():
        if token and token[0].isdigit() and "_" in token:
            return token.strip(".")
    return None
