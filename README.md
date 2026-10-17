# Fortitude Ranch — Daily App Report

Emails a manager a daily summary of:

- **Downloads** — new installs from the App Store (iOS) + Google Play (Android)
- **Subscriptions & revenue** — active subscriptions, active trials, MRR, revenue,
  new customers, and active users, from RevenueCat

The report is sent automatically each morning from your Gmail.

---

## How it works

```
daily_report.py      ← the main program (fetches everything, builds + sends the email)
revenuecat.py        ← RevenueCat subscriptions & revenue
appstore.py          ← iOS downloads (App Store Connect)
googleplay.py        ← Android downloads (Google Play reports)
emailer.py           ← sends the email via Gmail
run_report.sh        ← what the scheduler runs each morning
com.fortituderanch.dailyreport.plist  ← the daily 7:00 AM schedule
.env                 ← your credentials (you create this; never shared)
```

If one data source is unavailable, the email still goes out and notes which
part was missing.

> **A note on timing:** download numbers are not real-time. Apple finalizes a
> day's downloads about **1 day** later; Google Play's install reports lag
> **3–7 days**. So each download figure in the email is labeled with the exact
> date it represents. Subscription/revenue numbers from RevenueCat are current.

---

## One-time setup

### 0. Install (already done if you followed along)

```bash
cd /Users/ryangendel/Desktop/AppDailyReport
python3 -m venv venv
./venv/bin/python3 -m pip install -r requirements.txt
cp .env.example .env        # then fill in .env (steps below)
mkdir -p secrets            # put your .p8 and service-account.json here
```

Open `.env` in any text editor and fill in each value as you collect it below.

### 1. RevenueCat (subscriptions & revenue)

1. Go to the RevenueCat dashboard → your **Project → Settings → API keys → + New**.
2. Choose version **V2**, give it a name, and include the scope
   **`charts_metrics:overview:read`**. Generate it and copy the secret
   (starts with `atk_`). → `REVENUECAT_API_KEY`
3. **Project → Project Settings → General** → copy **Project ID**.
   → `REVENUECAT_PROJECT_ID`

### 2. App Store Connect (iOS downloads)

1. **Users and Access → Integrations → App Store Connect API** (Team Keys tab).
2. Copy the **Issuer ID** at the top. → `ASC_ISSUER_ID`
3. Click **+** to generate a key. Give it the **Sales** (or Finance/Admin) role.
   Copy the **Key ID**. → `ASC_KEY_ID`
4. **Download the `.p8` file** — you can only do this once. Save it to the
   `secrets/` folder and point `ASC_PRIVATE_KEY_PATH` at it.
5. **Payments and Financial Reports** → your **Vendor Number** (a number under
   your legal-entity name). → `ASC_VENDOR_NUMBER`

### 3. Google Play (Android downloads)

1. In **Google Cloud Console → IAM & Admin → Service Accounts → Create service
   account**. Copy its email (looks like `name@project.iam.gserviceaccount.com`).
2. On that service account → **Keys → Add key → Create new key → JSON**.
   Save the downloaded JSON into `secrets/` and point
   `GPLAY_SERVICE_ACCOUNT_FILE` at it.
3. In **Play Console → Users and permissions → Invite new user**, paste the
   service-account email and grant **"View app information and download bulk
   reports (read-only)" = Global**. (Do *not* use a Cloud IAM role for this.)
4. In **Play Console → Download reports**, click **Copy Cloud Storage URI**.
   Remove the `gs://` prefix and put the rest in `GPLAY_BUCKET`
   (e.g. `pubsite_prod_rev_0123456789`).
5. Set `GPLAY_PACKAGE_NAME` to your app id (e.g. `com.fortituderanch.app`).

### 4. Gmail (sending the email)

A standalone script can't use the Gmail linked inside Claude, so we use a
Gmail **App Password**:

1. Make sure **2-Step Verification** is on for `gendel.ryan@gmail.com`.
2. Go to <https://myaccount.google.com/apppasswords>, create an app password
   (name it "App Daily Report"), and copy the 16-character code.
   → `GMAIL_APP_PASSWORD` (paste it without spaces)
3. `REPORT_TO` is already set to `manager@fortituderanch.com`.

---

## Test it

Preview the report in your terminal (no email sent):

```bash
./venv/bin/python3 daily_report.py --dry-run
```

Send a real email right now (good for confirming Drew receives it):

```bash
./venv/bin/python3 daily_report.py
```

If a section shows `n/a`, the message next to it tells you which credential or
permission still needs fixing.

---

## Schedule it to run every morning (7:00 AM)

This uses macOS's built-in scheduler (`launchd`), which is more reliable than
cron — if your Mac is asleep at 7:00, it runs as soon as it wakes.

```bash
# Link the schedule into place
cp com.fortituderanch.dailyreport.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fortituderanch.dailyreport.plist
```

- **Change the send time:** edit `Hour`/`Minute` in the `.plist`, then
  `launchctl unload` and `launchctl load` it again.
- **Stop it:** `launchctl unload ~/Library/LaunchAgents/com.fortituderanch.dailyreport.plist`
- **Run it once immediately to test:**
  `launchctl start com.fortituderanch.dailyreport`
- Output is logged to `logs/report.log`.

> Your Mac must be powered on (asleep is fine) at the scheduled time for the
> email to send.

### Prefer classic cron instead?

```bash
crontab -e
# add this line (7:00 AM daily):
0 7 * * * /Users/ryangendel/Desktop/AppDailyReport/run_report.sh
```

---

## Run it in the cloud instead (GitHub Actions)

Prefer not to depend on your Mac being awake? The repo ships a scheduled
workflow at `.github/workflows/daily-report.yml` that runs the report in
GitHub's cloud every morning at **7:00 AM Mountain** (it fires at both 13:00
and 14:00 UTC and only sends at the real 7 AM, so it stays correct across
daylight-saving changes). You can also trigger it any time from the repo's
**Actions** tab → **Run workflow**.

Credentials are stored as encrypted **GitHub Actions secrets** — never in the
repo. Set them once with the GitHub CLI from your local files:

```bash
# simple values
gh secret set REVENUECAT_API_KEY      --body "<your value>"
gh secret set REVENUECAT_PROJECT_ID   --body "<your value>"
gh secret set ASC_ISSUER_ID           --body "<your value>"
gh secret set ASC_KEY_ID              --body "<your value>"
gh secret set ASC_VENDOR_NUMBER       --body "<your value>"
gh secret set GPLAY_BUCKET            --body "<your value>"
gh secret set GPLAY_PACKAGE_NAME      --body "<your value>"
gh secret set GMAIL_ADDRESS           --body "<your value>"
gh secret set GMAIL_APP_PASSWORD      --body "<your value>"
gh secret set REPORT_TO               --body "<recipient email>"

# file contents (whole file becomes the secret value)
gh secret set ASC_PRIVATE_KEY             < secrets/AuthKey_XXXX.p8
gh secret set GPLAY_SERVICE_ACCOUNT_JSON  < secrets/your-service-account.json
```

The workflow reconstructs the `.p8` and service-account files from those
secrets at run time and deletes them afterward.

---

## Security

Your local credentials live only in `.env` and the `secrets/` folder, both
excluded from version control by `.gitignore`. In the cloud they live only in
GitHub Actions secrets. Don't email, commit, or share those files.
