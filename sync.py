import os
import time
from datetime import datetime, timedelta, timezone
import requests
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mjmbpjulosdywzperdhe.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
ADZUNA_ID = os.environ.get("ADZUNA_APP_ID")
ADZUNA_KEY = os.environ.get("ADZUNA_APP_KEY")

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
                title = item.get("title", "").replace("<strong>", "").replace("</strong>", "")
                
                record = {
                    "title": title,
                    "company": item.get("company", {}).get("display_name", "Confidential"),
                    "location": item.get("location", {}).get("display_name", "United Kingdom"),
                    "job_description": item.get("description", ""),
                    "apply_url": item.get("redirect_url")
                }

                supabase.table("jobs").upsert(record, on_conflict="apply_url").execute()
                total_added += 1

            time.sleep(0.5)

        except Exception as e:
            print(f"Error fetching '{query}': {e}")

    print(f"\nBatch complete! Upserted {total_added} IT listings.")
    
    # Run auto-cleanup at the end of each sync run
    clean_expired_jobs(days=30)

if __name__ == "__main__":
    sync_high_volume_it_jobs()
