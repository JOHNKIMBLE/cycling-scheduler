#!/bin/bash
# Setup script for tiz-cycling-downloader on a seedbox or Linux server
# Usage: bash setup.sh

set -e

INSTALL_DIR="${TIZ_INSTALL_DIR:-$HOME/tiz-downloader}"
OUTPUT_DIR="${TIZ_OUTPUT_DIR:-$HOME/media/Cycling}"
VENV_DIR="$INSTALL_DIR/venv"

echo "=== Tiz-Cycling Downloader Setup ==="
echo ""

# Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$OUTPUT_DIR"

# Copy the script
echo "Installing downloader script..."
cp tiz_cycling_downloader.py "$INSTALL_DIR/"

# Create virtual environment
echo "Creating Python venv..."
python3 -m venv "$VENV_DIR"

# Install Python dependencies
echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet yt-dlp requests beautifulsoup4 lxml

echo "Installed: yt-dlp, requests, beautifulsoup4, lxml"

# Set up cron job (daily at 6 AM, check last 1 day)
CRON_CMD="0 6 * * * cd $INSTALL_DIR && $VENV_DIR/bin/python tiz_cycling_downloader.py --since 1 >> $HOME/tiz_downloader.log 2>&1"

if crontab -l 2>/dev/null | grep -q "tiz_cycling_downloader"; then
    echo "Updating existing cron job..."
    crontab -l 2>/dev/null | grep -v "tiz_cycling_downloader" | { cat; echo "$CRON_CMD"; } | crontab -
else
    echo "Adding daily cron job (6 AM)..."
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "  Install dir:  $INSTALL_DIR"
echo "  Output dir:   $OUTPUT_DIR"
echo "  Log file:     ~/tiz_downloader.log"
echo ""
echo "Usage:"
echo "  Dry run:      cd $INSTALL_DIR && $VENV_DIR/bin/python tiz_cycling_downloader.py --dry-run --since 1"
echo "  Run now:      cd $INSTALL_DIR && $VENV_DIR/bin/python tiz_cycling_downloader.py --since 1"
echo "  Single URL:   cd $INSTALL_DIR && $VENV_DIR/bin/python tiz_cycling_downloader.py --url 'https://tiz-cycling.tv/video/...'"
echo "  Check cron:   crontab -l"
echo "  View log:     tail -f ~/tiz_downloader.log"
echo ""
echo "Override defaults with environment variables:"
echo "  TIZ_OUTPUT_DIR=~/plex/sports/Cycling bash setup.sh"
