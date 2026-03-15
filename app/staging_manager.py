import logging
import os
import re
import shutil
import time
from datetime import datetime

logger = logging.getLogger('sonarr_youtubedl')

STAGING_DIR = '/staging'
STAGING_MAX_AGE_MINUTES = 60


def is_available():
    """Returns True if staging is usable - directory exists and is writable."""
    return os.path.isdir(STAGING_DIR) and os.access(STAGING_DIR, os.W_OK)


def ensure():
    """Create staging directory if it does not exist."""
    os.makedirs(STAGING_DIR, exist_ok=True)


def find_file(series_title, number):
    """Find a staged file by series title and episode number prefix."""
    prefix = f"{series_title} - {number}."
    for filename in os.listdir(STAGING_DIR):
        if filename.startswith(prefix):
            return os.path.join(STAGING_DIR, filename)
    return None


def staging_path(series_title, number):
    """Return the outtmpl staging path for a given episode."""
    return os.path.join(STAGING_DIR, f"{series_title} - {number}.%(ext)s")


def notify_sonarr(client, staging_file, sonarr_staging_path):
    """Tell Sonarr to import a staged file. Returns True if command was queued."""
    filename = os.path.basename(staging_file)
    sonarr_path = os.path.join(sonarr_staging_path, filename)
    response = client.downloaded_episodes_scan(sonarr_path)
    if 'id' not in response:
        logger.warning(f"Sonarr rejected import for: {filename}")
        return False
    logger.info(f"Sonarr notified - will import or fallback on next scan: {filename}")
    return True


def clean(client, season_format, path, localpath):
    """Remove or fall back stale staging files older than STAGING_MAX_AGE_MINUTES."""
    if not is_available():
        return

    now = datetime.now()
    for filename in os.listdir(STAGING_DIR):
        filepath = os.path.join(STAGING_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        age_minutes = (now - datetime.fromtimestamp(os.path.getmtime(filepath))).total_seconds() / 60
        if age_minutes > STAGING_MAX_AGE_MINUTES:
            logger.info(f"Staging file not imported after {STAGING_MAX_AGE_MINUTES}m: {filename}")
            _fallback(client, filepath, season_format, path, localpath)


def _fallback(client, staging_file, season_format, path, localpath):
    """Move a stale staging file to the library and trigger a Sonarr rescan."""
    name = os.path.splitext(os.path.basename(staging_file))[0]
    match = re.match(r'^(.+?) - (S\d+E\d+)$', name, re.IGNORECASE)
    if not match:
        logger.error(f"Cannot parse staging filename for fallback: {name}")
        return

    series_title, number = match.group(1), match.group(2)
    season_match = re.match(r'S(\d+)E\d+', number, re.IGNORECASE)
    if not season_match:
        return

    series_list = client.get_series()
    matched = next((s for s in series_list if s['title'] == series_title), None)
    if not matched:
        logger.error(f"Series not found in Sonarr for fallback: {series_title}")
        return

    series_path = matched['path'].replace(path, localpath) if path else os.path.join(localpath, series_title)
    season_dir = season_format.format(season=int(season_match.group(1)))
    ext = os.path.splitext(staging_file)[1]
    library_path = os.path.join(series_path, season_dir, f"{series_title} - {number} WEBDL{ext}")

    try:
        os.makedirs(os.path.dirname(library_path), exist_ok=True)
        shutil.move(staging_file, library_path)
        logger.info(f"Fallback: moved to library: {os.path.basename(library_path)}")
    except Exception as e:
        logger.error(f"Fallback move failed: {e}")
        return

    logger.info(f"Rescanning {series_title} in Sonarr")
    time.sleep(15)
    client.refresh(matched['id'])
    client.rescan(matched['id'])