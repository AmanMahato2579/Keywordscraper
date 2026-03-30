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

            # ✅ Timestamp extraction (improved)
            timestamp = None

            if obj.get("taken_at_timestamp"):
                timestamp = obj.get("taken_at_timestamp")

            elif obj.get("date"):
                timestamp = obj.get("date")

            elif obj.get("created_time"):
                timestamp = obj.get("created_time")

            elif "node" in obj and isinstance(obj["node"], dict):
                node = obj["node"]
                timestamp = (
                    node.get("taken_at_timestamp")
                    or node.get("date")
                    or node.get("created_time")
                )

            post_date = None
            if timestamp:
                try:
                    post_date = datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass

            if username:
                link = f"https://www.instagram.com/p/{shortcode}/"

                # Avoid overwriting good data with None
                if shortcode not in network_posts:
                    network_posts[shortcode] = {
                        "shortcode": shortcode,
                        "username": username,
                        "post_url": link,
                        "profile_link": f"https://www.instagram.com/{username}/",
                        "posted_date": post_date,
                    }
                else:
                    # Update only if date is missing
                    if not network_posts[shortcode]["posted_date"] and post_date:
                        network_posts[shortcode]["posted_date"] = post_date

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

        if "instagram.com" not in response.url:
            return

        data = await response.json()

        before = len(network_posts)
        extract_from_json(data)
        after = len(network_posts)

        if after > before:
            print(f"➕ {after-before} posts added | total: {after}")

    except:
        pass


# -----------------------------
# Get accurate post date (fallback)
# -----------------------------
async def get_post_date(page, url):
    try:
        await page.goto(url)
        await page.wait_for_timeout(2500)

        time_element = await page.query_selector("time")

        if time_element:
            return await time_element.get_attribute("datetime")

    except:
        return None


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
        await page.wait_for_timeout(6000)

        print("✅ Logged in")

        # 🔥 Scrape hashtag pages
        for tag in hashtags:
            print(f"\n🔥 Scraping #{tag}")

            url = f"https://www.instagram.com/explore/tags/{tag}/"
            await page.goto(url)
            await page.wait_for_timeout(7000)

            for i in range(20):
                await page.mouse.wheel(0, 5000)
                await page.wait_for_timeout(3000)

                print(f"Scroll {i+1}/20 — posts: {len(network_posts)}", end="\r")

        # 🔥 FIX missing dates
        print("\n⏳ Fetching missing post dates...")

        for post in network_posts.values():
            if not post["posted_date"]:
                post["posted_date"] = await get_post_date(page, post["post_url"])

        await browser.close()

    return list(network_posts.values())


# -----------------------------
# Save
# -----------------------------
def save(data):
    folder = "Results"
    os.makedirs(folder, exist_ok=True)

    user_choice = input("Enter filename (or press Enter for auto): ").strip()

    if user_choice:
        filename = user_choice.replace(" ", "_")
        if not filename.endswith(".csv"):
            filename += ".csv"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hashtag_results_{timestamp}.csv"

    filepath = os.path.join(folder, filename)

    df = pd.DataFrame(data)

    df = df.drop_duplicates("shortcode")
    df = df.drop_duplicates("profile_link")

    df.to_csv(filepath, index=False)

    print(f"✅ Saved {len(df)} records → {filepath}")


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    data = asyncio.run(scrape())
    save(data)