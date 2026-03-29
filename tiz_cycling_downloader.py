#!/usr/bin/env python3
"""
Tiz-Cycling Auto-Downloader for Plex

Automatically downloads full cycling race videos from tiz-cycling.tv
and organizes them in a Plex-friendly folder structure with metadata.

Folder layout:
  Cycling/
    Race Name (2026-03-28)/
      Race Name 2026 - Full Race (2026-03-28).mp4
      Race Name 2026 - Full Race (2026-03-28).nfo
      poster.jpg
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, unquote, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

# --- Configuration (override via CLI flags or env vars) ---
SITE_URL = os.environ.get("TIZ_SITE_URL", "https://tiz-cycling.tv")
OUTPUT_DIR = os.environ.get("TIZ_OUTPUT_DIR", os.path.expanduser("~/media/Cycling"))
HISTORY_FILE = os.environ.get("TIZ_HISTORY_FILE", os.path.expanduser("~/.tiz_downloaded.json"))
LOG_FILE = os.environ.get("TIZ_LOG_FILE", os.path.expanduser("~/tiz_downloader.log"))
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
REQUEST_DELAY = 1.0  # seconds between HTTP requests


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def setup_logging(log_file=LOG_FILE):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"downloaded": []}


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    })
    # Hit homepage first to pick up Cloudflare cookies
    try:
        session.get(SITE_URL, timeout=15)
    except requests.RequestException:
        pass
    return session


# ---------------------------------------------------------------------------
# Race metadata parsing
# ---------------------------------------------------------------------------

def parse_race_info(title, url=""):
    """Parse race name, year, stage, and type from title/URL.

    Returns dict with keys: race_name, year, stage, race_type, folder_name, file_name
    """
    slug = url.rstrip("/").split("/")[-1] if url else ""

    # Determine race type
    race_type = "Full Race"
    if "full-stage" in slug or re.search(r"\bfull.?stage\b", title, re.IGNORECASE):
        race_type = "Full Stage"

    # Clean the slug into a readable title
    clean = slug
    clean = re.sub(r"-full-race$|-full-stage$", "", clean)
    clean = re.sub(r"-ladies$", " Ladies", clean)
    clean = re.sub(r"-spanish$|-italian$|-japanese$|-french$|-german$|-dutch$|-flemish$|-thai$|-mandarin$|-vietnamese$|-rwandan$|-slovenian$", "", clean)
    clean = clean.replace("-", " ").strip()
    clean = clean.title()
    if not clean:
        clean = title
        clean = re.sub(r"\s*\[Full (Stage|Race)\]\s*", " ", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*[-|]\s*Tiz.*$", "", clean, flags=re.IGNORECASE)
        clean = clean.strip()

    # Extract year
    year_match = re.search(r"(20\d{2})", clean)
    year = year_match.group(1) if year_match else str(datetime.now().year)

    # Extract stage number
    stage_match = re.search(r"(?:stage|etapa|tappa|etape)\s*(\d+)", clean, re.IGNORECASE)
    stage = stage_match.group(1) if stage_match else None

    # Extract race name
    race_name = clean
    race_name = re.sub(r"\s*20\d{2}\s*", " ", race_name)
    race_name = re.sub(r"\s*[-\u2013]\s*(?:stage|etapa|tappa|etape)\s*\d+\s*", " ", race_name, flags=re.IGNORECASE)
    race_name = re.sub(r"\s*(?:stage|etapa|tappa|etape)\s*\d+\s*", " ", race_name, flags=re.IGNORECASE)
    race_name = re.sub(r'[<>:"/\\|?*]', "", race_name)
    race_name = re.sub(r"\s+", " ", race_name).strip()
    race_name = re.sub(r"^[-\u2013\s]+|[-\u2013\s]+$", "", race_name)

    if not race_name or len(race_name) < 3:
        slug = url.rstrip("/").split("/")[-1]
        slug = re.sub(r"-full-race$|-full-stage$", "", slug)
        slug = re.sub(r"-20\d{2}$", "", slug)
        race_name = slug.replace("-", " ").title()

    # Folder name (date appended later in process_post)
    folder_name = race_name
    folder_name = re.sub(r'[<>:"/\\|?*]', "", folder_name)

    # File name
    if stage:
        file_name = f"{race_name} {year} - Stage {stage}"
    else:
        file_name = f"{race_name} {year} - {race_type}"
    file_name = re.sub(r'[<>:"/\\|?*]', "", file_name)

    return {
        "race_name": race_name,
        "year": year,
        "stage": stage,
        "race_type": race_type,
        "folder_name": folder_name,
        "file_name": file_name,
        "original_title": title,
    }


# ---------------------------------------------------------------------------
# Plex metadata (.nfo + poster)
# ---------------------------------------------------------------------------

def write_nfo(nfo_path, race_info, url, dry_run=False):
    """Write a Plex-compatible .nfo metadata file."""
    if dry_run:
        logging.info(f"[DRY RUN] Would write NFO: {nfo_path}")
        return

    movie = ET.Element("movie")
    ET.SubElement(movie, "title").text = race_info["file_name"]
    ET.SubElement(movie, "year").text = race_info["year"]
    ET.SubElement(movie, "genre").text = "Cycling"
    ET.SubElement(movie, "genre").text = "Sports"
    ET.SubElement(movie, "studio").text = "Tiz-Cycling"
    ET.SubElement(movie, "plot").text = (
        f"{race_info['race_name']} {race_info['year']}"
        + (f" - Stage {race_info['stage']}" if race_info["stage"] else "")
        + f" ({race_info['race_type']})"
    )
    ET.SubElement(movie, "outline").text = race_info["original_title"]
    if race_info.get("date"):
        ET.SubElement(movie, "premiered").text = race_info["date"]
        ET.SubElement(movie, "aired").text = race_info["date"]
    ET.SubElement(movie, "tag").text = race_info["race_name"]
    ET.SubElement(movie, "tag").text = f"Cycling {race_info['year']}"
    if race_info["stage"]:
        ET.SubElement(movie, "tag").text = f"Stage {race_info['stage']}"
    ET.SubElement(movie, "dateadded").text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    tree = ET.ElementTree(movie)
    ET.indent(tree, space="  ")
    tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
    logging.info(f"Wrote NFO: {nfo_path}")


def download_thumbnail(session, page_url, output_dir, dry_run=False):
    """Try to grab a thumbnail/poster image from the video page."""
    if dry_run:
        logging.info(f"[DRY RUN] Would download thumbnail for: {page_url}")
        return

    try:
        resp = session.get(page_url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        img_url = og_image["content"]
    else:
        tw_image = soup.find("meta", attrs={"name": "twitter:image"})
        if tw_image and tw_image.get("content"):
            img_url = tw_image["content"]
        else:
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if any(skip in src.lower() for skip in ["logo", "icon", "avatar", "gravatar"]):
                    continue
                img_url = urljoin(page_url, src)
                break
            else:
                return

    poster_path = os.path.join(output_dir, "poster.jpg")
    if os.path.exists(poster_path):
        return

    try:
        img_resp = session.get(img_url, timeout=30)
        img_resp.raise_for_status()
        with open(poster_path, "wb") as f:
            f.write(img_resp.content)
        logging.info(f"Downloaded poster: {poster_path}")
    except requests.RequestException as e:
        logging.warning(f"Could not download thumbnail: {e}")


# ---------------------------------------------------------------------------
# Sitemap parsing
# ---------------------------------------------------------------------------

def get_video_sitemaps(session):
    """Fetch the sitemap index to find all video sitemap URLs."""
    sitemap_url = f"{SITE_URL}/sitemap.xml"
    logging.info(f"Fetching sitemap index: {sitemap_url}")
    try:
        resp = session.get(sitemap_url, timeout=30)
    except requests.RequestException as e:
        logging.error(f"Failed to fetch sitemap index: {e}")
        return []

    if "<sitemap" not in resp.text and "<urlset" not in resp.text:
        logging.error(f"Sitemap index returned no XML (status {resp.status_code})")
        return []

    soup = BeautifulSoup(resp.text, "xml")
    video_sitemaps = []
    for sitemap in soup.find_all("sitemap"):
        loc = sitemap.find("loc")
        if loc and "posts-video" in loc.text:
            video_sitemaps.append(loc.text)

    logging.info(f"Found {len(video_sitemaps)} video sitemaps")
    return video_sitemaps


def parse_sitemap_entries(session, sitemap_url):
    """Parse a sitemap XML and return list of (url, lastmod_date) tuples."""
    entries = []
    try:
        resp = session.get(sitemap_url, timeout=30)
    except requests.RequestException:
        return entries

    if "<urlset" not in resp.text:
        return entries

    soup = BeautifulSoup(resp.text, "xml")
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        if not loc:
            continue
        url = loc.text.strip()

        lastmod = url_tag.find("lastmod")
        mod_date = None
        if lastmod and lastmod.text:
            try:
                mod_date = datetime.fromisoformat(lastmod.text.strip())
            except ValueError:
                pass

        entries.append((url, mod_date))
    return entries


def scrape_recent_posts(session, since_days=7):
    """Scrape video URLs from sitemaps, filtered to entries newer than since_days."""
    posts = []
    video_sitemaps = get_video_sitemaps(session)
    if not video_sitemaps:
        logging.error("No video sitemaps found")
        return posts

    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    logging.info(f"Looking for videos newer than {cutoff.strftime('%Y-%m-%d')}")

    for sitemap_url in reversed(video_sitemaps[-3:]):
        logging.info(f"Fetching sitemap: {sitemap_url}")
        time.sleep(REQUEST_DELAY)
        entries = parse_sitemap_entries(session, sitemap_url)

        if not entries:
            logging.warning(f"No entries from {sitemap_url}")
            continue

        for url, mod_date in entries:
            if mod_date and mod_date < cutoff:
                continue
            if not mod_date:
                continue

            slug = url.rstrip("/").split("/")[-1]
            title = slug.replace("-", " ").title()
            date_str = mod_date.strftime("%Y-%m-%d")
            posts.append({"url": url, "title": title, "description": "", "date": date_str})

        if posts:
            logging.info(f"Found {len(posts)} video posts from last {since_days} days")
            break

    if not posts:
        logging.warning(f"No videos found in the last {since_days} days")
    return posts


# ---------------------------------------------------------------------------
# Video URL extraction
# ---------------------------------------------------------------------------

def is_full_race(post):
    """Check if a post is a full race based on URL slug."""
    url = post.get("url", "").lower()
    slug = url.rstrip("/").split("/")[-1]
    return "full-race" in slug or "full-stage" in slug


def extract_real_mp4(url):
    """Extract the actual mp4 URL from a video.php?v= wrapper URL."""
    if "video.php" in url and "v=" in url:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if "v" in params:
            return params["v"][0]
    return url


def find_mp4_url(session, page_url):
    """Try to find a direct CDN mp4 URL from the page source."""
    logging.info(f"Inspecting page for mp4: {page_url}")
    try:
        resp = session.get(page_url, timeout=30)
    except requests.RequestException as e:
        logging.error(f"Failed to fetch page {page_url}: {e}")
        return None

    logging.info(f"Page status: {resp.status_code}, length: {len(resp.text)}")
    if len(resp.text) < 500:
        logging.warning(f"Page too short, likely blocked. Content: {resp.text[:200]}")
        return None

    text = resp.text

    # Method 1: Find CDN direct URL (most reliable)
    marker = "video.tiz-cycling.io/file/"
    idx = text.find(marker)
    if idx != -1:
        start = text.rfind("https://", max(0, idx - 50), idx)
        if start == -1:
            start = text.rfind("http://", max(0, idx - 50), idx)
        if start != -1:
            end = start
            for end in range(start, min(start + 500, len(text))):
                if text[end] in '"\'<> \t\n\r':
                    break
            mp4_url = text[start:end]
            mp4_url = extract_real_mp4(mp4_url)
            logging.info(f"Found mp4: {mp4_url}")
            return mp4_url

    # Method 2: Find any .mp4 reference pointing to CDN
    idx = text.find(".mp4")
    while idx != -1:
        start = text.rfind("https://", max(0, idx - 500), idx)
        if start != -1:
            end = idx + 4
            while end < len(text) and text[end] not in '"\'<> \t\n\r':
                end += 1
            mp4_url = text[start:end]
            if "video.tiz-cycling" in mp4_url or "file/Tiz" in mp4_url:
                mp4_url = extract_real_mp4(mp4_url)
                logging.info(f"Found mp4 via search: {mp4_url}")
                return mp4_url
        idx = text.find(".mp4", idx + 4)

    logging.warning("No mp4 URL found in page")
    return None


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_video(url, output_path, dry_run=False):
    """Download video using yt-dlp."""
    if dry_run:
        logging.info(f"[DRY RUN] Would download: {url}")
        logging.info(f"[DRY RUN] Output: {output_path}")
        return True

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-check-certificates",
        "-o", output_path,
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--retries", "1",
        "--fragment-retries", "1",
        url,
    ]

    logging.info(f"Running: {' '.join(cmd)}")
    try:
        if sys.stdout.isatty():
            result = subprocess.run(cmd, timeout=7200)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if result.returncode == 0:
            logging.info(f"Downloaded successfully: {output_path}")
            return True
        else:
            stderr = result.stderr[:500] if hasattr(result, "stderr") and result.stderr else "unknown error"
            logging.warning(f"yt-dlp failed (rc={result.returncode}): {stderr}")
            return False
    except subprocess.TimeoutExpired:
        logging.error("Download timed out after 2 hours")
        return False
    except FileNotFoundError:
        logging.error("yt-dlp not found. Install it: pip install yt-dlp")
        return False


# ---------------------------------------------------------------------------
# Post processing pipeline
# ---------------------------------------------------------------------------

def process_post(session, post, history, dry_run=False):
    """Process a single post: extract video, download, write metadata."""
    url = post["url"]
    title = post["title"]

    logging.info(f"Checking: {title}")

    race_info = parse_race_info(title, url)
    race_info["date"] = post.get("date", "")

    # Append date to filename if available
    file_name = race_info["file_name"]
    if race_info["date"]:
        file_name = f"{file_name} ({race_info['date']})"

    # Put airdate in folder name so Plex picks it up
    folder_name = race_info["folder_name"]
    if race_info["date"]:
        folder_name = f"{folder_name} ({race_info['date']})"

    logging.info(f"Parsed: {folder_name} / {file_name}")

    race_dir = os.path.join(OUTPUT_DIR, folder_name)
    output_path = os.path.join(race_dir, f"{file_name}.mp4")
    nfo_path = os.path.join(race_dir, f"{file_name}.nfo")

    # Skip if already downloaded
    if os.path.exists(output_path):
        logging.info(f"Already exists, skipping: {file_name}")
        return False
    if url in history["downloaded"]:
        logging.info(f"Already in history, skipping: {file_name}")
        return False

    os.makedirs(race_dir, exist_ok=True)

    # Extract the direct CDN mp4 URL from the page
    mp4_url = find_mp4_url(session, url)
    if mp4_url:
        logging.info(f"Downloading mp4: {mp4_url}")
        downloaded = download_video(mp4_url, output_path, dry_run)
    else:
        # No CDN mp4 — skip (YouTube-hosted videos are not supported)
        logging.info(f"No CDN video found, skipping: {title}")
        return False

    if downloaded:
        write_nfo(nfo_path, race_info, url, dry_run)
        download_thumbnail(session, url, race_dir, dry_run)

        if not dry_run:
            history["downloaded"].append(url)
            save_history(history)
        return True

    logging.warning(f"Could not download: {title} ({url})")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global OUTPUT_DIR

    parser = argparse.ArgumentParser(
        description="Auto-download full cycling race videos for Plex",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --since 1              # Download full races from the last day
  %(prog)s --since 7 --dry-run    # Preview what would download from last week
  %(prog)s --url URL              # Download a specific race page
  %(prog)s --output ~/plex/sports # Override output directory

Environment variables:
  TIZ_OUTPUT_DIR    Output directory (default: ~/media/Cycling)
  TIZ_HISTORY_FILE  Download history JSON (default: ~/.tiz_downloaded.json)
  TIZ_LOG_FILE      Log file path (default: ~/tiz_downloader.log)
        """,
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without downloading")
    parser.add_argument("--output", default=OUTPUT_DIR, help=f"Output directory (default: {OUTPUT_DIR})")
    parser.add_argument("--url", help="Download a specific race page URL")
    parser.add_argument("--since", type=int, default=7, metavar="DAYS",
                        help="Only check videos from the last N days (default: 7)")
    args = parser.parse_args()

    OUTPUT_DIR = args.output

    setup_logging()
    logging.info("=" * 60)
    logging.info(f"Tiz-Cycling Downloader started at {datetime.now()}")
    if args.dry_run:
        logging.info("DRY RUN MODE - no downloads will occur")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    history = load_history()
    session = get_session()

    if args.url:
        slug = args.url.rstrip("/").split("/")[-1]
        title = slug.replace("-", " ").title()
        post = {"url": args.url, "title": title, "description": "[Full Race]", "date": ""}
        process_post(session, post, history, args.dry_run)
        return

    posts = scrape_recent_posts(session, since_days=args.since)
    full_races = [p for p in posts if is_full_race(p)]
    logging.info(f"Found {len(full_races)} full races out of {len(posts)} recent videos")

    downloaded = 0
    for i, post in enumerate(full_races):
        if i > 0:
            time.sleep(3)
        if process_post(session, post, history, args.dry_run):
            downloaded += 1

    logging.info(f"Done. Downloaded {downloaded} new races.")
    logging.info("=" * 60)


if __name__ == "__main__":
    main()
