"""Fetch subscription/revenue metrics from the RevenueCat v2 Overview API.

Endpoint: GET https://api.revenuecat.com/v2/projects/{project_id}/metrics/overview
Auth:     Authorization: Bearer <V2 secret key, prefixed 'atk_'>
          Key needs the scope: charts_metrics:overview:read

Returns the six dashboard-overview numbers. Per-product (monthly vs annual)
splits are NOT available on this endpoint — they require the Charts API or a
data export, which we intentionally skip to keep this simple.
"""

import requests

BASE_URL = "https://api.revenuecat.com/v2"

# metric id -> friendly label, in the order we want to show them
METRIC_LABELS = {
    "active_subscriptions": "Active subscriptions",
    "active_trials": "Active trials",
    "mrr": "MRR (monthly recurring revenue)",
    "revenue": "Revenue (last 28 days)",
    "new_customers": "New customers (last 28 days)",
    "active_users": "Active users (last 28 days)",
}


def get_overview(api_key, project_id, timeout=30):
    """Return a dict with the overview metrics plus formatting helpers.

    Shape:
        {
          "currency": "USD",
          "metrics": {
             "active_subscriptions": {"value": 123, "unit": "#", "label": "..."},
             ...
          }
        }
    """
    url = f"{BASE_URL}/projects/{project_id}/metrics/overview"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    metrics = {}
    for m in data.get("metrics", []):
        metrics[m["id"]] = {
            "value": m.get("value"),
            "unit": m.get("unit", "#"),
            "label": METRIC_LABELS.get(m["id"], m.get("name", m["id"])),
        }

    return {"currency": data.get("currency", "USD"), "metrics": metrics}


def format_metric(entry, currency):
    """Format a single metric value for display ($ vs count)."""
    value = entry.get("value")
    if value is None:
        return "n/a"
    if entry.get("unit") == "$":
        return f"{currency} {value:,.2f}"
    return f"{value:,}"
