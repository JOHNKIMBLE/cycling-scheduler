# tiz-cycling-downloader

Auto-download full cycling race videos from [tiz-cycling.tv](https://tiz-cycling.tv) for Plex. Runs on a seedbox or any Linux server with Python 3 and cron.

## What it does

- Checks the site's sitemap for new video posts
- Filters for **full races and full stages only** (skips highlights, last 20km clips, etc.)
- Downloads the CDN-hosted mp4 directly via yt-dlp
- Organizes into Plex-friendly folders with `.nfo` metadata and poster art
- Tracks downloads so it never re-downloads the same video
- Runs daily via cron, only checking the last N days

## Folder structure

```
Cycling/
  E3 Saxo Classic (2026-03-28)/
    E3 Saxo Classic 2026 - Full Race (2026-03-28).mp4
    E3 Saxo Classic 2026 - Full Race (2026-03-28).nfo
    poster.jpg
  Volta Ciclista A Catalunya (2026-03-27)/
    Volta Ciclista A Catalunya 2026 - Stage 5 (2026-03-27).mp4
    Volta Ciclista A Catalunya 2026 - Stage 5 (2026-03-27).nfo
    poster.jpg
```

## Quick start

```bash
git clone https://github.com/JOHNKIMBLE/cycling-scheduler.git
cd cycling-scheduler
bash setup.sh
```

This creates a Python venv, installs dependencies, and adds a daily cron job at 6 AM.

## Usage

```bash
cd ~/tiz-downloader

# Preview what would download from the last day
venv/bin/python tiz_cycling_downloader.py --dry-run --since 1

# Download full races from the last 3 days
venv/bin/python tiz_cycling_downloader.py --since 3

# Download a specific race by URL
venv/bin/python tiz_cycling_downloader.py --url 'https://tiz-cycling.tv/video/e3-saxo-classic-2026-full-race/'

# Override output directory
venv/bin/python tiz_cycling_downloader.py --output ~/plex/sports/Cycling --since 1
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--since DAYS` | `7` | Only check videos from the last N days |
| `--dry-run` | off | Preview without downloading |
| `--output DIR` | `~/media/Cycling` | Output directory for Plex |
| `--url URL` | - | Download a single race page |

## Environment variables

Override defaults without CLI flags:

| Variable | Default | Description |
|----------|---------|-------------|
| `TIZ_OUTPUT_DIR` | `~/media/Cycling` | Output directory |
| `TIZ_HISTORY_FILE` | `~/.tiz_downloaded.json` | Download history |
| `TIZ_LOG_FILE` | `~/tiz_downloader.log` | Log file path |

## How it works

1. Fetches the WordPress sitemap index from tiz-cycling.tv
2. Parses the latest video sitemap for entries with `lastmod` dates within the `--since` window
3. Filters for URLs containing `full-race` or `full-stage` in the slug
4. For each new race, scrapes the video page to extract the direct CDN mp4 URL
5. Downloads via yt-dlp with progress output (interactive) or silently (cron)
6. Writes Plex `.nfo` sidecar with title, year, genre, air date, and tags
7. Grabs the `og:image` thumbnail as `poster.jpg`

## Notes

- Only CDN-hosted videos are downloaded. Some smaller/foreign-language races are YouTube-only and will be skipped.
- The site uses Cloudflare, so the script warms up cookies and avoids Brotli encoding.
- Sitemap responses may return HTTP 404 with valid XML content (Cloudflare quirk) - the script handles this.
- Rate limiting: 1s delay between sitemap requests, 3s between video downloads.

## Requirements

- Python 3.8+
- Linux/macOS (seedbox, VPS, etc.)
- cron (for automated daily runs)
- ~5-10 GB free per race (full races are typically 3-8 GB)

## Dependencies

Installed automatically by `setup.sh`:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - video download
- [requests](https://docs.python-requests.org/) - HTTP client
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) - HTML/XML parsing
- [lxml](https://lxml.de/) - fast XML parser

## License

MIT
