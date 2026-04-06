# AGENTS.md

## Purpose

This repository is a small, single-script downloader for cycling race videos published on `tiz-cycling.tv`. Its job is to:

- discover recent Tiz video posts from the WordPress sitemap
- keep only posts that look like full races or full stages
- inspect each post page to find the actual playable video source
- download that source with `yt-dlp`
- organize the result into a Plex-friendly folder with sidecar metadata
- remember what was already downloaded so repeat runs are cheap and safe

Default output path in the current codebase is `~/files/sports/Cycling`.

The most important current implementation detail is this:

- the downloader does not scrape video bytes itself
- it scrapes the Tiz page for a playable source URL, then hands that URL to `yt-dlp`
- this is intentionally kept simple because `yt-dlp` already handles direct mp4, YouTube, retries, and remuxing much better than a custom downloader would

## Current Supported Video Sources

At the time of writing, Tiz pages commonly expose one of these patterns:

1. A Tiz CDN iframe such as `https://tiz-cycling.tv/video.php?v=https://video.tiz-cycling.io/file/...mp4`
2. A direct Tiz CDN mp4 somewhere in the page HTML
3. A YouTube embed such as `https://www.youtube.com/embed/<id>?start=<seconds>`

The downloader now supports both families:

- Tiz CDN-hosted videos
- YouTube-hosted videos embedded on the Tiz race page

Implementation note:

- YouTube support is still powered by `yt-dlp`
- the script only needs to detect and normalize the YouTube URL
- there is no separate YouTube download stack in this repo

## High-Level Flow

The end-to-end flow is:

1. Build a `requests.Session` with browser-like headers and warm Cloudflare cookies by visiting the homepage.
2. Fetch `https://tiz-cycling.tv/sitemap.xml`.
3. Extract `posts-video` sitemap URLs from the sitemap index.
4. Read the newest video sitemap files and keep entries newer than `--since`.
5. Convert each recent sitemap entry into a lightweight post dict with `url`, `title`, and `date`.
6. Filter to slugs containing `full-race` or `full-stage`.
7. For each candidate post:
8. Parse race metadata from the title/slug.
9. Skip if the output file already exists or the page URL is already in history.
10. Fetch the Tiz post page and extract a downloadable source URL.
11. Pass the extracted source URL to `yt-dlp`.
12. If download succeeds, write `.nfo`, download `poster.jpg`, and save the page URL to history.

## File Map

### [`tiz_cycling_downloader.py`](/c:/Users/Conno/Desktop/Projects/tiz-cycling-downloader/tiz_cycling_downloader.py)

This is the whole application. There is no package layout yet. Major sections:

- configuration constants and environment overrides
- HTTP session setup
- race metadata parsing
- Plex metadata writing
- sitemap discovery/parsing
- video source extraction
- download execution through `yt-dlp`
- per-post processing pipeline
- CLI entrypoint

### [`setup.sh`](/c:/Users/Conno/Desktop/Projects/tiz-cycling-downloader/setup.sh)

Linux/seedbox bootstrap script. It:

- creates the install directory and output directory
- copies the Python script and onboarding docs into the install directory
- creates a virtualenv
- installs Python dependencies
- installs a local Deno runtime inside the install directory
- generates `tiz-env.sh` inside the install directory
- creates or updates a daily cron job

### [`setup.ps1`](/c:/Users/Conno/Desktop/Projects/tiz-cycling-downloader/setup.ps1)

Windows bootstrap script. It:

- creates the install directory and output directory
- copies the Python script and onboarding docs into the install directory
- creates a virtualenv
- installs Python dependencies
- installs a local Deno runtime inside the install directory
- generates `tiz-env.ps1` and `run-tiz.ps1` inside the install directory
- creates or updates a daily Scheduled Task

### [`README.md`](/c:/Users/Conno/Desktop/Projects/tiz-cycling-downloader/README.md)

User-facing overview and quick start. Keep this shorter and task-focused.

### [`release.ps1`](/c:/Users/Conno/Desktop/Projects/tiz-cycling-downloader/release.ps1)

Local helper for pushing to GitHub. This is not part of runtime behavior.

## Core Runtime Concepts

### Post dict shape

The script passes around small post dicts shaped like:

```python
{
    "url": "https://tiz-cycling.tv/video/...",
    "title": "Dwars Door Vlaanderen 2026 Full Race",
    "description": "",
    "date": "2026-04-02",
}
```

These come from sitemap entries, not from a richer page scraper.

### History file

History is stored as JSON:

```json
{
  "downloaded": [
    "https://tiz-cycling.tv/video/example-full-race/"
  ]
}
```

Current semantics:

- history is keyed by the Tiz page URL, not by the underlying CDN or YouTube URL
- if Tiz changes the embedded source but keeps the same page URL, the script will still consider it already downloaded
- the output file existence check is the other guard against re-downloads

### Folder and file naming

Current code behavior:

- `file_name` is derived from parsed race metadata
- `folder_name` is currently set equal to `file_name`
- the race date is written into the `.nfo` when available, rather than being appended to the folder/file name

Example:

```text
Cycling/
  Dwars Door Vlaanderen 2026 - Full Race/
    Dwars Door Vlaanderen 2026 - Full Race.mp4
    Dwars Door Vlaanderen 2026 - Full Race.nfo
    poster.jpg
```

If this naming strategy changes again, update both README and this file because it affects Plex behavior and user expectations.

## Video Source Extraction

This is the most important subsystem in the repo.

### Why it exists

Tiz post pages do not always expose the final downloadable URL directly in one clean place. The script has to inspect the page and detect which host is actually serving the video.

### Current strategy

The extractor now works in layers:

1. Parse the HTML with BeautifulSoup.
2. Inspect common source-bearing tags: `iframe`, `video`, `source`, `a`, and `meta`.
3. Check common attributes: `src`, `data-src`, `data-lazy-src`, `href`, and `content`.
4. Normalize HTML entities and escaped URLs.
5. Prefer Tiz CDN sources first.
6. If no CDN source is found, look for YouTube embeds/links.
7. Fall back to raw string/regex scanning of the page HTML.

### URL normalization helpers

Important helper behaviors:

- `clean_candidate_url()` unescapes HTML entities and strips quotes
- `extract_real_mp4()` unwraps `video.php?v=...` URLs
- `normalize_youtube_url()` converts embed or short-form YouTube URLs into a normal `watch?v=` URL and preserves `start` where available

### Why YouTube uses yt-dlp

This project already depends on `yt-dlp`, so the simplest reliable design is:

- scrape page
- extract source URL
- hand source URL to `yt-dlp`

Trying to download YouTube without `yt-dlp` would add a lot of complexity and fragility for little gain.

## Race Metadata Parsing

`parse_race_info()` is heuristic and slug-driven. It tries to infer:

- race name
- year
- stage number
- race type (`Full Race` vs `Full Stage`)

Important assumptions:

- full stage detection is based on slug/title matching
- language suffixes like `-spanish`, `-thai`, `-vietnamese`, etc. are stripped from the readable race name
- stage extraction supports several multilingual keywords such as `stage`, `etapa`, `tappa`, and `etape`

If naming quality becomes a problem, this function is the first place to improve.

## Plex Metadata

`write_nfo()` writes a simple movie-style `.nfo` with:

- title
- year
- genre
- studio
- plot
- outline
- premiered/aired date when available
- tags
- dateadded

`download_thumbnail()` fetches `og:image`, then falls back to `twitter:image`, then finally a best-effort `<img>` scan.

This is intentionally lightweight. The downloader is not trying to be a full metadata agent.

## Setup and Deployment

### Expected environment

Primary targets are:

- Linux seedboxes or VPS machines with Python 3.8+ and cron
- Windows machines with Python 3.8+ and Task Scheduler
- enough disk for large race videos

### Installed dependencies

`setup.sh` / `setup.ps1` currently install:

- `yt-dlp[default]`
- `requests`
- `beautifulsoup4`
- `lxml`
- a local Deno runtime at `<install dir>/deno/bin/deno`

Important note:

- `beautifulsoup4` is already part of setup
- there is no additional packaging work needed just to support HTML parsing
- the install is intended to be self-contained under the install directory rather than depending on shell profile edits

### Generated env file

The setup scripts now write a local env file:

- `<install dir>/tiz-env.sh` on Linux
- `<install dir>/tiz-env.ps1` on Windows

That file is the supported way to load the contained runtime environment:

- prepends the local Deno binary to `PATH`
- exports `TIZ_OUTPUT_DIR`
- exports `TIZ_YTDLP_JS_RUNTIMES` pointing at the local Deno binary
- keeps YouTube cookie handling simple by expecting `youtube-cookies.txt` to live next to the script

On Windows, `setup.ps1` also writes `<install dir>/run-tiz.ps1` as the normal entrypoint for manual runs and the Scheduled Task.

### YouTube auth/runtime knobs

The downloader now supports optional yt-dlp pass-through settings for harder YouTube cases:

- `--cookies` / `TIZ_YTDLP_COOKIES`
- `--cookies-from-browser` / `TIZ_YTDLP_COOKIES_FROM_BROWSER`
- `--js-runtimes` / `TIZ_YTDLP_JS_RUNTIMES`
- `--remote-components` / `TIZ_YTDLP_REMOTE_COMPONENTS`

These are intentionally thin pass-throughs to yt-dlp rather than a custom auth layer.

In the current setup model, the easiest path is:

- run `. ./tiz-env.sh`
- place `youtube-cookies.txt` in the install directory
- let the script auto-detect that cookie file and the local Deno runtime

### Scheduler model

The setup scripts create a daily automation entry that runs the downloader with `--since 1`:

- cron on Linux
- Scheduled Task on Windows

That means the normal production model is incremental:

- check last day
- skip anything already in history
- download only newly published full races/stages

## Known Quirks and Gotchas

### Cloudflare and sitemap behavior

The site is inconsistent enough that the code already contains defensive logic:

- homepage warm-up to collect cookies
- browser-like request headers
- sitemap parsing that trusts XML content even when site behavior is odd

### Very large HTML pages

Some Tiz pages are huge. The extractor therefore mixes DOM-based parsing with cheap raw-text fallback scanning.

### Direct page URL is the durable identifier

History tracks page URLs, not source URLs. That is usually what we want, but it matters for debugging.

### Local cookie/runtime autodetection

If the install directory contains these files, the script will auto-use them when env vars are not explicitly set:

- `youtube-cookies.txt`
- `deno/bin/deno`

This is deliberate. It keeps the install contained to one folder on both Linux and Windows.

### There are no automated tests yet

There is currently no test suite. Verification is mostly:

- syntax check
- dry run against a known CDN page
- dry run against a known YouTube-backed page
- direct `yt-dlp` test against a known YouTube URL when debugging auth/runtime issues
- manual inspection of logs/output

## Safe Change Guide

If a future agent needs to modify this repo, the safest order of operations is:

1. Read the whole script once because behavior is centralized.
2. Check `git diff` before editing because the repo may be locally dirty.
3. Inspect a live sample page from Tiz before changing extraction logic.
4. Prefer small helper functions over large rewrites.
5. Preserve the existing `yt-dlp` handoff unless there is a very strong reason to replace it.
6. Preserve the contained install model in `setup.sh` unless there is a strong reason to move back to shell-profile-based setup.
7. Update README and this file together when user-facing behavior changes.

## Recommended Future Improvements

These are reasonable next steps if the project grows:

- add a small test fixture set with saved HTML samples for CDN and YouTube pages
- split the single script into modules once extraction logic grows further
- add clearer logging around which source type was selected
- optionally support a configurable “download non-full-race posts” mode
- add a lightweight health check command that only validates extraction
- pin `yt-dlp` versions in environments where reproducibility matters
- optionally bundle or verify ffmpeg if seedbox environments start missing it often

## Decision Log

Current design decisions that should remain true unless intentionally changed:

- keep the app as a single script until complexity justifies modularization
- keep `yt-dlp` as the actual downloader for both CDN and YouTube
- keep the sitemap-first discovery approach because it is cheap and reliable
- keep history idempotency simple and page-URL-based
- prefer simple heuristics over heavy parsing unless the site changes enough to force it
- keep the install self-contained under the install directory, including the Deno runtime
- keep Linux and Windows setup parity where practical so onboarding stays simple

## Fast Onboarding Checklist

If you are new to this repo, read in this order:

1. [`README.md`](/c:/Users/Conno/Desktop/Projects/tiz-cycling-downloader/README.md)
2. [`AGENTS.md`](/c:/Users/Conno/Desktop/Projects/tiz-cycling-downloader/AGENTS.md)
3. [`tiz_cycling_downloader.py`](/c:/Users/Conno/Desktop/Projects/tiz-cycling-downloader/tiz_cycling_downloader.py)
4. the `process_post()` function
5. the `find_video_url()` and related helper functions
6. `setup.sh` or `setup.ps1` for the target platform

If something breaks in production, start with:

- whether the sitemap still returns recent posts
- whether the Tiz page still contains a recognizable CDN or YouTube source
- whether `yt-dlp` still works in that environment
- whether history is causing a false skip
