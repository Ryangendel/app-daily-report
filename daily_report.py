#!/usr/bin/env python3
"""Daily App Report — emails Drew a summary of downloads + RevenueCat subscriptions.

Run it manually:   python3 daily_report.py
Test without email: python3 daily_report.py --dry-run   (prints the report instead)

Each data source is fetched independently; if one fails, the email still goes
out with the others and notes what was unavailable. Downloads lag behind real
time (iOS ~1 day, Google Play 3-7 days), so each number is labeled with the
actual date it represents.
"""

import argparse
import datetime as dt
import os
import sys

from dotenv import load_dotenv

import appstore
import emailer
import googleplay
import revenuecat

load_dotenv()


def _env(name, required=True, default=None):
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required setting {name} in .env")
    return val


def _load_p8():
    """Return the App Store Connect .p8 private key text (from path or inline)."""
    path = os.environ.get("ASC_PRIVATE_KEY_PATH")
    if path and os.path.exists(path):
        with open(path, "r") as fh:
            return fh.read()
    inline = os.environ.get("ASC_PRIVATE_KEY")
    if inline:
        return inline.replace("\\n", "\n")
    raise RuntimeError("Set ASC_PRIVATE_KEY_PATH (or ASC_PRIVATE_KEY) in .env")


def gather():
    """Collect all sections. Each entry: (ok, payload_or_error_string)."""
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    results = {}

    # --- RevenueCat subscriptions + revenue ---
    try:
        results["revenuecat"] = ("ok", revenuecat.get_overview(
            _env("REVENUECAT_API_KEY"), _env("REVENUECAT_PROJECT_ID")))
    except Exception as e:
        results["revenuecat"] = ("error", str(e))

    # --- iOS downloads (App Store Connect) ---
    try:
        ios = appstore.get_downloads(
            _env("ASC_ISSUER_ID"), _env("ASC_KEY_ID"), _load_p8(),
            _env("ASC_VENDOR_NUMBER"), yesterday.strftime("%Y-%m-%d"))
        if ios is None:
            # yesterday not finalized yet — walk back a few days
            for i in range(2, 6):
                d = (today - dt.timedelta(days=i)).strftime("%Y-%m-%d")
                ios = appstore.get_downloads(
                    _env("ASC_ISSUER_ID"), _env("ASC_KEY_ID"), _load_p8(),
                    _env("ASC_VENDOR_NUMBER"), d)
                if ios is not None:
                    results["ios"] = ("ok", {"date": d, "downloads": ios})
                    break
            else:
                results["ios"] = ("error", "no finalized report available yet")
        else:
            results["ios"] = ("ok", {"date": yesterday.strftime("%Y-%m-%d"),
                                     "downloads": ios})
    except Exception as e:
        results["ios"] = ("error", str(e))

    # --- Android downloads (Google Play) ---
    try:
        android = googleplay.get_downloads(
            _env("GPLAY_SERVICE_ACCOUNT_FILE"), _env("GPLAY_BUCKET"),
            _env("GPLAY_PACKAGE_NAME"), today)
        if android is None:
            results["android"] = ("error", "no install report available yet")
        else:
            results["android"] = ("ok", {"date": android["date"],
                                         "downloads": android["installs"]})
    except Exception as e:
        results["android"] = ("error", str(e))

    return results


def render(results):
    """Build (subject, text_body, html_body) from gathered results."""
    today_str = dt.date.today().strftime("%A, %B %-d, %Y")
    subject = f"Fortitude Ranch App — Daily Report ({dt.date.today():%b %-d})"

    lines = [f"Daily App Report — {today_str}", "=" * 40, ""]
    html = [
        "<div style='font-family:-apple-system,Segoe UI,Arial,sans-serif;"
        "max-width:560px;color:#1a1a1a'>",
        f"<h2 style='margin:0 0 4px'>Fortitude Ranch App — Daily Report</h2>",
        f"<p style='color:#666;margin:0 0 20px'>{today_str}</p>",
    ]

    # ---- Downloads ----
    lines.append("DOWNLOADS (new installs)")
    html.append("<h3 style='margin:18px 0 6px'>Downloads <span style='font-weight:normal;"
                "color:#888;font-size:13px'>(new installs)</span></h3>")
    total_dl = 0
    have_total = True
    html.append("<table style='border-collapse:collapse;width:100%'>")
    for key, platform in (("ios", "iOS (App Store)"), ("android", "Android (Google Play)")):
        status, payload = results[key]
        if status == "ok":
            n = payload["downloads"]
            total_dl += n
            lines.append(f"  {platform:<22} {n:>6,}   (as of {payload['date']})")
            html.append(
                f"<tr><td style='padding:4px 0'>{platform}</td>"
                f"<td style='text-align:right;font-weight:600'>{n:,}</td>"
                f"<td style='color:#999;font-size:12px;padding-left:10px'>as of {payload['date']}</td></tr>")
        else:
            have_total = False
            lines.append(f"  {platform:<22}   n/a   ({payload})")
            html.append(
                f"<tr><td style='padding:4px 0'>{platform}</td>"
                f"<td style='text-align:right;color:#b00'>n/a</td>"
                f"<td style='color:#999;font-size:12px;padding-left:10px'>{payload}</td></tr>")
    if have_total:
        lines.append(f"  {'TOTAL':<22} {total_dl:>6,}")
        html.append(
            f"<tr style='border-top:1px solid #ddd'><td style='padding:6px 0;font-weight:700'>Total</td>"
            f"<td style='text-align:right;font-weight:700'>{total_dl:,}</td><td></td></tr>")
    html.append("</table>")
    lines.append("")

    # ---- Subscriptions / revenue (RevenueCat) ----
    lines.append("SUBSCRIPTIONS & REVENUE (RevenueCat)")
    html.append("<h3 style='margin:22px 0 6px'>Subscriptions &amp; Revenue</h3>")
    status, payload = results["revenuecat"]
    if status == "ok":
        currency = payload["currency"]
        html.append("<table style='border-collapse:collapse;width:100%'>")
        for mid in revenuecat.METRIC_LABELS:
            entry = payload["metrics"].get(mid)
            if not entry:
                continue
            value = revenuecat.format_metric(entry, currency)
            lines.append(f"  {entry['label']:<34} {value}")
            html.append(
                f"<tr><td style='padding:4px 0'>{entry['label']}</td>"
                f"<td style='text-align:right;font-weight:600'>{value}</td></tr>")
        html.append("</table>")
    else:
        lines.append(f"  n/a ({payload})")
        html.append(f"<p style='color:#b00'>Unavailable: {payload}</p>")

    lines += ["", "-" * 40,
              "Download figures lag real time (iOS ~1 day, Google Play 3-7 days),",
              "so each is labeled with the date it represents.",
              "Automated report. RevenueCat revenue is gross, before store fees."]
    html.append(
        "<p style='color:#999;font-size:12px;margin-top:22px'>Download figures lag real time "
        "(iOS ~1 day, Google Play 3&ndash;7 days), so each is labeled with the date it represents. "
        "RevenueCat revenue is gross, before store fees. Automated daily report.</p></div>")

    return subject, "\n".join(lines), "\n".join(html)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the report instead of emailing it")
    args = parser.parse_args()

    results = gather()
    subject, text_body, html_body = render(results)

    if args.dry_run:
        print(subject)
        print()
        print(text_body)
        return

    emailer.send_email(
        host=_env("SMTP_HOST", default="smtp.gmail.com", required=False),
        port=int(_env("SMTP_PORT", default="587", required=False)),
        username=_env("GMAIL_ADDRESS"),
        app_password=_env("GMAIL_APP_PASSWORD"),
        sender=_env("GMAIL_ADDRESS"),
        to=_env("REPORT_TO", default="manager@fortituderanch.com", required=False),
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
    print(f"Sent report to {_env('REPORT_TO', default='manager@fortituderanch.com', required=False)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
