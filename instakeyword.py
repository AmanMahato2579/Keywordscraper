import asyncio
from datetime import datetime
import os
import pandas as pd
from playwright.async_api import async_playwright

network_posts = {}


# -----------------------------
# Extract JSON (POSTS)
# -----------------------------
def extract_from_json(obj):
    global network_posts

    if isinstance(obj, dict):

        shortcode = obj.get("shortcode") or obj.get("code")

        if shortcode:
            username = None

            if "owner" in obj and isinstance(obj["owner"], dict):
                username = obj["owner"].get("username")

            if not username:
                username = obj.get("username")

            # ✅ NEW: extract timestamp
            timestamp = (
                obj.get("taken_at_timestamp")
                or obj.get("date")
                or obj.get("created_time")
            )

            post_date = None
            if timestamp:
                try:
                    post_date = datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    post_date = None

            if username:

                link = f"https://www.instagram.com/p/{shortcode}/"

                network_posts[shortcode] = {
                    "shortcode": shortcode,
                    "username": username,
                    "post_url": link,
                    "profile_link": f"https://www.instagram.com/{username}/",
                    "posted_date": post_date,   # ✅ NEW FIELD
                }
        for v in obj.values():
            extract_from_json(v)

    elif isinstance(obj, list):
        for i in obj:
            extract_from_json(i)


# -----------------------------
# Network listener
# -----------------------------
async def on_response(response):

    try:

        content_type = response.headers.get("content-type", "")

        if "json" not in content_type:
            return

        url = response.url

        # SMALL CHANGE: allow more Instagram endpoints
        if "instagram.com" not in url:
            return

        # DEBUG: show where data comes from
        if "graphql" in url or "api" in url or "tags" in url:
            print("📡 Captured API:", url)

        data = await response.json()

        before = len(network_posts)

        extract_from_json(data)

        after = len(network_posts)

        # show if new posts added
        if after > before:
            print(f"➕ {after-before} posts added | total: {after}")

    except:
        pass


# -----------------------------
# Load hashtags
# -----------------------------
def load_hashtags(file="hashtags.txt"):

    with open(file, "r", encoding="utf-8") as f:
        return [line.strip().lstrip("#") for line in f if line.strip()]


# -----------------------------
# Scrape hashtags
# -----------------------------
async def scrape():

    hashtags = load_hashtags()

    async with async_playwright() as p:

        browser = await p.chromium.launch_persistent_context(
            user_data_dir="insta_session",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = await browser.new_page()

        page.on("response", on_response)

        await page.goto("https://www.instagram.com")
        await page.wait_for_timeout(5000)

        print("✅ Logged in")

        for tag in hashtags:

            print(f"\n🔥 Scraping #{tag}")

            url = f"https://www.instagram.com/explore/tags/{tag}/"

            await page.goto(url)

            await page.wait_for_timeout(6000)

            # SCROLL
            for i in range(20):

                await page.mouse.wheel(0, 4000)

                await page.wait_for_timeout(2000)

                print(
                    f"Scroll {i+1}/20 — posts: {len(network_posts)}",
                    end="\r"
                )

        await browser.close()

    return list(network_posts.values())


# -----------------------------
# Save
# -----------------------------
def save(data, filename=None):
    folder = "Results"
    os.makedirs(folder, exist_ok=True)
    
    user_choice = input("Enter the filename to save (or press Enter for default): ").strip()
    
    # 1. Handle filename logic
    if user_choice:
        # Replace spaces with underscores and ensure .csv extension
        filename = user_choice.replace(" ", "_")
        if not filename.lower().endswith(".csv"):
            filename += ".csv"
    else:
        # Fallback to timestamp if user just hits Enter
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hashtag_results_{timestamp}.csv"


    filepath = os.path.join(folder, filename)
    
    # 2. Process Data
    df = pd.DataFrame(data)
    
    # Drop duplicates (inplace=True or reassigning works)
    df = df.drop_duplicates(subset=["shortcode"])
    df = df.drop_duplicates(subset=["profile_link"])

    # 3. Save
    df.to_csv(filepath, index=False)

    print(f"✅ Saved {len(df)} records to {filepath}")

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":

    data = asyncio.run(scrape())

    save(data)