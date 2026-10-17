"""Fetch daily Android installs from the Google Play statistics-reports bucket.

Google Play has no installs *API* — the only source of install counts is the
monthly CSV in the Cloud Storage bucket Play Console exposes:

    gs://pubsite_prod_rev_<account-id>/stats/installs/
        installs_<packageName>_YYYYMM_overview.csv

Important: these reports lag 3-7 days, so the latest available day is usually
several days behind. We read the most recent date present in the file and
report both the number and the date it refers to.

Auth: a Google Cloud service-account JSON key whose *service-account email* has
been granted "View app information and download bulk reports (read-only) =
Global" in Play Console -> Users and permissions. (NOT a Cloud IAM role.)
"""

import csv
import datetime as dt
import io

from google.cloud import storage
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/devstorage.read_only"]
INSTALLS_COLUMN = "Daily Device Installs"  # install events incl. reinstalls


def _client(service_account_file):
    creds = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=SCOPES)
    return storage.Client(credentials=creds, project=creds.project_id)


def _download_csv(client, bucket_name, package_name, yyyymm):
    """Return list-of-dict rows for one monthly overview CSV, or [] if absent."""
    blob_path = f"stats/installs/installs_{package_name}_{yyyymm}_overview.csv"
    blob = client.bucket(bucket_name).blob(blob_path)
    if not blob.exists():
        return []
    # Play exports these CSVs as UTF-16 (LE w/ BOM).
    text = blob.download_as_bytes().decode("utf-16")
    return list(csv.DictReader(io.StringIO(text)))


def get_downloads(service_account_file, bucket_name, package_name, as_of_date,
                  lookback_days=14):
    """Return the most recent available daily installs on/before `as_of_date`.

    `as_of_date` is a datetime.date. Returns a dict:
        {"date": "YYYY-MM-DD", "installs": int}  or  None if nothing found.
    Reads the current and previous month files to cover month boundaries.
    """
    client = _client(service_account_file)

    months = {as_of_date.strftime("%Y%m"),
              (as_of_date.replace(day=1) - dt.timedelta(days=1)).strftime("%Y%m")}

    # date (str) -> installs (int), for every row we can read
    by_date = {}
    for yyyymm in months:
        for row in _download_csv(client, bucket_name, package_name, yyyymm):
            date_str = (row.get("Date") or "").strip()
            raw = (row.get(INSTALLS_COLUMN) or "").strip()
            if not date_str:
                continue
            try:
                by_date[date_str] = int(float(raw)) if raw else 0
            except ValueError:
                continue

    # Walk back from as_of_date to find the most recent day present.
    for i in range(lookback_days + 1):
        day = (as_of_date - dt.timedelta(days=i)).strftime("%Y-%m-%d")
        if day in by_date:
            return {"date": day, "installs": by_date[day]}
    return None
