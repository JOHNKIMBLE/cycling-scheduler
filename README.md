# tiz-cycling-downloader

Auto-download full cycling race videos from [tiz-cycling.tv](https://tiz-cycling.tv) for Plex. Runs on Linux seedboxes and Windows machines with Python 3.

Default output path: `~/files/sports/Cycling`

## What it does

- Checks the site's sitemap for new video posts
- Filters for **full races and full stages only** (skips highlights, last 20km clips, etc.)
- Downloads either the Tiz CDN-hosted mp4 or a YouTube embed via yt-dlp
- Organizes into Plex-friendly folders with `.nfo` metadata and poster art
- Tracks downloads so it never re-downloads the same video
- Runs daily via cron, only checking the last N days

## Folder structure

```
Cycling/
  E3 Saxo Classic 2026 - Full Race/
    E3 Saxo Classic 2026 - Full Race.mp4
    E3 Saxo Classic 2026 - Full Race.nfo
    poster.jpg
  Volta Ciclista A Catalunya 2026 - Stage 5/
    Volta Ciclista A Catalunya 2026 - Stage 5.mp4
    Volta Ciclista A Catalunya 2026 - Stage 5.nfo
    poster.jpg
```

## Quick start

Linux / seedbox:

```bash
git clone https://github.com/JOHNKIMBLE/cycling-scheduler.git
cd cycling-scheduler
bash setup.sh
```

Windows PowerShell:

```powershell
git clone https://github.com/JOHNKIMBLE/cycling-scheduler.git
cd cycling-scheduler
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Both setup scripts create a self-contained install in `~/tiz-downloader` with:

- a Python venv
- local `yt-dlp` dependencies
- a local Deno runtime in `~/tiz-downloader/deno`
- a generated env file at `~/tiz-downloader/tiz-env.sh` on Linux or `~/tiz-downloader/tiz-env.ps1` on Windows
- a daily scheduler entry at 6 AM

## Usage

Linux / seedbox:

```bash
cd ~/tiz-downloader
. ./tiz-env.sh

# Preview what would download from the last day
venv/bin/python tiz_cycling_downloader.py --dry-run --since 1

# Download full races from the last 3 days
venv/bin/python tiz_cycling_downloader.py --since 3

# Download a specific race by URL
venv/bin/python tiz_cycling_downloader.py --url 'https://tiz-cycling.tv/video/e3-saxo-classic-2026-full-race/'

# Download YouTube-backed races with exported browser cookies
cp ~/youtube-cookies.txt ~/tiz-downloader/youtube-cookies.txt
venv/bin/python tiz_cycling_downloader.py --since 1
```

Windows PowerShell:

```powershell
Set-Location ~/tiz-downloader
. .\tiz-env.ps1

# Preview what would download from the last day
.\run-tiz.ps1 -DryRun -Since 1

# Download full races from the last 3 days
.\run-tiz.ps1 -Since 3

# Download a specific race by URL
.\run-tiz.ps1 -Url 'https://tiz-cycling.tv/video/e3-saxo-classic-2026-full-race/'

# Download YouTube-backed races with exported browser cookies
Copy-Item ~/Downloads/youtube-cookies.txt ~/tiz-downloader/youtube-cookies.txt -Force
.\run-tiz.ps1 -Since 1
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--since DAYS` | `7` | Only check videos from the last N days |
| `--dry-run` | off | Preview without downloading |
| `--output DIR` | `~/files/sports/Cycling` | Output directory for Plex |
| `--url URL` | - | Download a single race page |
| `--cookies FILE` | off | Pass a cookies.txt file through to yt-dlp |
| `--cookies-from-browser SPEC` | off | Pass a browser profile through to yt-dlp |
| `--js-runtimes VALUE` | off | Pass JS runtime config through to yt-dlp |
| `--remote-components VALUE` | off | Pass remote component config through to yt-dlp |

## Environment variables

Override defaults without CLI flags:

| Variable | Default | Description |
|----------|---------|-------------|
| `TIZ_OUTPUT_DIR` | `~/files/sports/Cycling` | Output directory |
| `TIZ_HISTORY_FILE` | `~/.tiz_downloaded.json` | Download history |
| `TIZ_LOG_FILE` | `~/tiz_downloader.log` | Log file path |
| `TIZ_YTDLP_COOKIES` | unset | cookies.txt passed through to yt-dlp |
| `TIZ_YTDLP_COOKIES_FROM_BROWSER` | unset | Browser profile passed through to yt-dlp |
| `TIZ_YTDLP_JS_RUNTIMES` | unset | JS runtime(s) for yt-dlp, e.g. `deno` |
| `TIZ_YTDLP_REMOTE_COMPONENTS` | unset | Optional yt-dlp remote components, e.g. `ejs:github` |

## How it works

1. Fetches the WordPress sitemap index from tiz-cycling.tv
2. Parses the latest video sitemap for entries with `lastmod` dates within the `--since` window
3. Filters for URLs containing `full-race` or `full-stage` in the slug
4. For each new race, scrapes the video page to extract either the direct CDN mp4 URL or an embedded YouTube URL
5. Downloads via yt-dlp with progress output (interactive) or silently (cron)
6. Writes Plex `.nfo` sidecar with title, year, genre, air date, and tags
7. Grabs the `og:image` thumbnail as `poster.jpg`

## Notes

- YouTube-backed race pages are supported by extracting the embed URL and handing it to yt-dlp.
- Some YouTube videos now require cookies and a JS runtime in yt-dlp. If you hit a bot-check error, export a `cookies.txt` file and pass `--cookies ~/youtube-cookies.txt` or set `TIZ_YTDLP_COOKIES`.
- If YouTube auth is missing or fails, that post is skipped and the script continues. CDN-hosted races will still download normally.
- `setup.sh` and `setup.ps1` install a local Deno runtime into the install directory and generate a local env file, so YouTube support no longer depends on shell profile edits.
- If `~/tiz-downloader/youtube-cookies.txt` exists, the downloader auto-detects it even without `--cookies`.
- On Windows, `setup.ps1` creates a daily Scheduled Task that runs while your user account is logged in.
- The site uses Cloudflare, so the script warms up cookies and avoids Brotli encoding.
- Sitemap responses may return HTTP 404 with valid XML content (Cloudflare quirk) - the script handles this.
- Rate limiting: 1s delay between sitemap requests, 3s between video downloads.

## Easy YouTube setup

If a Tiz page points at YouTube and yt-dlp says `Sign in to confirm you're not a bot`, do this:

1. On your own computer, open a private/incognito browser window.
2. Log into YouTube in that private window.
3. In the same tab, open `https://www.youtube.com/robots.txt`.
4. Export `youtube.com` cookies to a file named `youtube-cookies.txt`.
5. Copy that file to the machine running the downloader.
6. Put it at `~/tiz-downloader/youtube-cookies.txt`.
7. Run the downloader from the install directory after loading `tiz-env.sh` or `tiz-env.ps1`.

Example commands:

```bash
# Linux / seedbox: copy cookie file from your local computer to the seedbox
scp ~/Downloads/youtube-cookies.txt treasurefingers@kore:~/youtube-cookies.txt

# On the seedbox, put the cookie file in the install dir and run the downloader
cd ~/tiz-downloader
cp ~/youtube-cookies.txt ~/tiz-downloader/youtube-cookies.txt
. ./tiz-env.sh
venv/bin/python tiz_cycling_downloader.py --since 1
```

Windows PowerShell:

```powershell
Copy-Item ~/Downloads/youtube-cookies.txt ~/tiz-downloader/youtube-cookies.txt -Force
Set-Location ~/tiz-downloader
. .\tiz-env.ps1
.\run-tiz.ps1 -Since 1
```

If you want to test yt-dlp directly with the contained runtime, use:

```bash
cd ~/tiz-downloader
. ./tiz-env.sh
venv/bin/python -m yt_dlp \
  --cookies ~/tiz-downloader/youtube-cookies.txt \
  --js-runtimes "deno:$HOME/tiz-downloader/deno/bin/deno" \
  "https://www.youtube.com/watch?v=kfE6yVr6dnA"
```

Tips:

- The cookie file must be in Netscape/Mozilla `cookies.txt` format.
- Keep the cookie file private. It can authenticate you.
- If downloads start failing again later, export a fresh cookie file and replace the old one.

## Requirements

- Python 3.8+
- Linux/macOS or Windows
- cron on Linux or Task Scheduler on Windows for automated daily runs
- ~5-10 GB free per race (full races are typically 3-8 GB)

## Dependencies

Installed automatically by `setup.sh` / `setup.ps1`:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) with the `default` extras - video download and bundled EJS support files
- [requests](https://docs.python-requests.org/) - HTTP client
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) - HTML/XML parsing
- [lxml](https://lxml.de/) - fast XML parser
- [Deno](https://deno.com/) installed locally under the install directory for YouTube JS challenge solving

## License

MIT
