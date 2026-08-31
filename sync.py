import os
import time
import requests
from supabase import create_client

# Reads from environment variables (GitHub Secrets or Terminal env)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mjmbpjulosdywzperdhe.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
ADZUNA_ID = os.environ.get("ADZUNA_APP_ID")
ADZUNA_KEY = os.environ.get("ADZUNA_APP_KEY")

if not SUPABASE_KEY or not ADZUNA_ID or not ADZUNA_KEY:
    raise ValueError("Missing required environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def sync_uk_it_jobs(pages_to_fetch=11):
    total_inserted = 0
    print("Starting sync for UK Information Technology (IT) jobs...")

    for page in range(1, pages_to_fetch + 1):
        print(f"Fetching IT jobs page {page} of {pages_to_fetch}...")
        
        url = (
            f"https://api.adzuna.com/v1/api/jobs/gb/search/{page}"
            f"?app_id={ADZUNA_ID}"
            f"&app_key={ADZUNA_KEY}"
            f"&results_per_page=50"
            f"&category=it-jobs"
            f"&content-type=application/json"
        )

        try:
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                print(f"Failed to fetch page {page}: {response.status_code}")
                continue

            jobs = response.json().get("results", [])
            if not jobs:
                print("No more IT jobs returned.")
                break

            for item in jobs:
                title = item.get("title", "").replace("<strong>", "").replace("</strong>", "")
                
                record = {
                    "title": title,
                    "company": item.get("company", {}).get("display_name", "Confidential"),
                    "location": item.get("location", {}).get("display_name", "United Kingdom"),
                    "job_description": item.get("description", ""),
                    "apply_url": item.get("redirect_url")
                }

                supabase.table("jobs").upsert(record, on_conflict="apply_url").execute()
                total_inserted += 1

            time.sleep(0.3)

        except Exception as e:
            print(f"Error on page {page}: {e}")

    print(f"\nSync complete! Successfully processed {total_inserted} UK IT jobs.")

if __name__ == "__main__":
    sync_uk_it_jobs(pages_to_fetch=11)
