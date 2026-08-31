import os
import time
from datetime import datetime, timedelta, timezone
import requests
import resend
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mjmbpjulosdywzperdhe.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
ADZUNA_ID = os.environ.get("ADZUNA_APP_ID")
ADZUNA_KEY = os.environ.get("ADZUNA_APP_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
ALERT_FROM_EMAIL = os.environ.get("ALERT_FROM_EMAIL")

if not SUPABASE_KEY or not ADZUNA_ID or not ADZUNA_KEY:
    raise ValueError("Missing environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

IT_KEYWORDS = [
    "developer",
    "software engineer",
    "data engineer",
    "devops",
    "cloud architect",
    "cyber security",
    "it support",
    "qa engineer",
    "solution architect",
    "full stack"
]

def clean_expired_jobs(days=30):
    """Deletes job listings older than the specified number of days to keep database fresh."""
    try:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        print(f"Cleaning jobs older than {days} days (before {cutoff_date})...")
        res = supabase.table("jobs").delete().lt("created_at", cutoff_date).execute()
        print("Database cleanup completed successfully.")
    except Exception as e:
        print(f"Cleanup notice/skipped: {e}")

def send_job_alerts():
    """Send matching jobs to active job-alert subscribers."""
    if not RESEND_API_KEY or not ALERT_FROM_EMAIL:
        print("Job alerts skipped: Resend configuration is missing.")
        return

    resend.api_key = RESEND_API_KEY

    try:
        alerts_response = (
            supabase
            .table("job_alerts")
            .select("*")
            .eq("active", True)
            .execute()
        )

        alerts = alerts_response.data or []

        if not alerts:
            print("No active job alerts found.")
            return

        jobs_response = (
            supabase
            .table("jobs")
            .select("*")
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )

        jobs = jobs_response.data or []

        for alert in alerts:
            email = alert.get("email")
            keywords = (alert.get("keywords") or "").lower()
            location = (alert.get("location") or "").lower()
            remote_only = alert.get("remote_only", False)

            if not email or not keywords:
                continue

            keyword_list = [
                keyword.strip()
                for keyword in keywords.split(",")
                if keyword.strip()
            ]

            matching_jobs = []

            for job in jobs:
                searchable_text = " ".join([
                    job.get("title") or "",
                    job.get("company") or "",
                    job.get("location") or "",
                    job.get("job_description") or ""
                ]).lower()

                if not any(keyword in searchable_text for keyword in keyword_list):
                    continue

                if location and location not in searchable_text:
                    continue

                if remote_only:
                    if "remote" not in searchable_text:
                        continue

                matching_jobs.append(job)

            if not matching_jobs:
                continue

            # Limit each email to the 10 most recent matches.
            matching_jobs = matching_jobs[:10]

            job_rows = ""

            for job in matching_jobs:
                title = job.get("title") or "IT Job"
                company = job.get("company") or "Company"
                job_location = job.get("location") or "United Kingdom"
                apply_url = job.get("apply_url") or "#"

                job_rows += f"""
                <li style="margin-bottom: 18px;">
                    <strong>{title}</strong><br>
                    {company}<br>
                    {job_location}<br>
                    <a href="{apply_url}">View & Apply</a>
                </li>
                """


            unsubscribe_url = (
                "https://mjmbpjulosdywzperdhe.supabase.co"
                "/functions/v1/unsubscribe-alert"
                f"?token={alert.get('unsubscribe_token', '')}"
            )

            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #0f172a;">
                <h2>New UK IT Jobs matching your alert</h2>

                <p>
                    We found <strong>{len(matching_jobs)}</strong>
                    job(s) matching your alert.
                </p>

                <ul>
                    {job_rows}
                </ul>

                <p>
                    You're receiving this email because you created
                    a job alert on UK IT Jobs.
                </p>

                <hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;">

                <p style="font-size:12px;color:#64748b;">
                    Don't want these emails anymore?
                    <a href="{unsubscribe_url}"
                       style="color:#059669;">
                        Unsubscribe from this job alert
                    </a>
                </p>
            </body>
            </html>
            """


            try:
                resend.Emails.send({
                    "from": ALERT_FROM_EMAIL,
                    "to": [email],
                    "subject": "New UK IT jobs matching your alert",
                    "html": html,
                })

                print(
                    f"Alert email sent to {email} "
                    f"({len(matching_jobs)} matching jobs)."
                )

                # Record when this alert was notified.
                if alert.get("id"):
                    supabase.table("job_alerts").update({
                        "last_notified_at": datetime.now(timezone.utc).isoformat()
                    }).eq("id", alert["id"]).execute()

            except Exception as e:
                print(f"Failed to send alert to {email}: {e}")

    except Exception as e:
        print(f"Job alert processing failed: {e}")

def sync_high_volume_it_jobs():
    total_added = 0
    print("Starting max-yield IT job harvesting across UK...")

    for query in IT_KEYWORDS:
        print(f"Fetching IT vacancies for keyword: '{query}'...")

        url = (
            f"https://api.adzuna.com/v1/api/jobs/gb/search/1"
            f"?app_id={ADZUNA_ID}"
            f"&app_key={ADZUNA_KEY}"
            f"&results_per_page=50"
            f"&category=it-jobs"
            f"&what={requests.utils.quote(query)}"
            f"&content-type=application/json"
        )

        try:
            res = requests.get(url, timeout=15)

            if res.status_code != 200:
                print(f"Failed query '{query}': HTTP {res.status_code}")
                continue

            results = res.json().get("results", [])

            for item in results:
                title = (
                    item.get("title", "")
                    .replace("<strong>", "")
                    .replace("</strong>", "")
                )

                record = {
                    "title": title,
                    "company": item.get("company", {}).get(
                        "display_name",
                        "Confidential"
                    ),
                    "location": item.get("location", {}).get(
                        "display_name",
                        "United Kingdom"
                    ),
                    "job_description": item.get("description", ""),
                    "apply_url": item.get("redirect_url"),
                    "salary_min": item.get("salary_min"),
                    "salary_max": item.get("salary_max")
                }

                supabase.table("jobs").upsert(
                    record,
                    on_conflict="apply_url"
                ).execute()

                total_added += 1

            time.sleep(0.5)

        except Exception as e:
            print(f"Error fetching '{query}': {e}")

    print(f"\nBatch complete! Upserted {total_added} IT listings.")

    # Run auto-cleanup at the end of each sync run
    clean_expired_jobs(days=30)

    # Send matching job alerts
    send_job_alerts()


if __name__ == "__main__":
    sync_high_volume_it_jobs()
