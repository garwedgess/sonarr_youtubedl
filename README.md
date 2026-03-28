# sonarr_youtubedl by [@garwedgess](https://github.com/garwedgess)
![CI](https://github.com/garwedgess/sonarr_youtubedl/actions/workflows/build.yml/badge.svg)

> Originally forked from [@whatdaybob](https://github.com/whatdaybob/sonarr_youtubedl)

[sonarr_youtubedl](https://github.com/garwedgess/sonarr_youtubedl) is a [Sonarr](https://sonarr.tv/) companion script to allow automatic downloading of web series normally unavailable to Sonarr. Using [yt-dlp](https://github.com/yt-dlp/yt-dlp) it downloads from any of the [supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) and imports directly into your Sonarr library.

## Features

- Automatic downloading of web series from YouTube and other supported sites
- Imports via Sonarr's `DownloadedEpisodesScan` for proper history entries
- Fuzzy title matching with regex pre-filter - handles title mismatches between TVDB and YouTube
- PO token support via [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) for authenticated YouTube access
- Telegram and webhook notifications on download start and completion
- Per-series configuration: custom format, cookies, subtitles, time offsets, regex title cleanup, scan intervals, yt-dlp options
- Duplicate file protection - skips downloads if file already exists in library or staging
- Optional staging directory for clean separation between downloads and media library
- Automatic exponential backoff on YouTube rate limiting

## How it works

1. Sonarr is polled for monitored, missing, aired episodes
2. For each missing episode the YouTube channel or playlist is fetched
3. The episode title is matched against playlist entries using regex, with fuzzy matching as fallback
4. The video is downloaded to a staging directory (if configured) or directly to the library
5. Sonarr is notified to import the file, creating a history entry
6. If Sonarr doesn't import within 60 minutes the file is moved to the library directly as fallback

## Supported Architectures

| Architecture | Tag |
| :---: | --- |
| x86-64 | latest |
| arm64 | latest |
| x86-64 | dev |
| arm64 | dev |

## Getting Started

You need a series available on a yt-dlp supported site, added and monitored in Sonarr, and a `config.yml` pointing to both.

### docker-compose (recommended)

```yaml
services:
  sonarr_youtubedl:
    image: wedgess/sonarr_youtubedl:latest
    container_name: sonarr-youtubedl
    volumes:
      - /path/to/appdata/sonarr_ytdl/config:/config
      - /path/to/media/tvshows:/sonarr_root
      - /path/to/appdata/sonarr_ytdl/logs:/logs
      - /path/to/downloads/sonarr_youtubedl:/staging  # optional, see Staging below
    environment:
      PUID: 1000
      PGID: 1000
    restart: unless-stopped
    depends_on:
      sonarr:
        condition: service_healthy
```

### docker

```bash
docker create \
  --name=sonarr-youtubedl \
  -v /path/to/appdata/sonarr_ytdl/config:/config \
  -v /path/to/media/tvshows:/sonarr_root \
  -v /path/to/appdata/sonarr_ytdl/logs:/logs \
  -v /path/to/downloads/sonarr_youtubedl:/staging \
  -e PUID=1000 \
  -e PGID=1000 \
  --restart unless-stopped \
  wedgess/sonarr_youtubedl:latest
```

### Volumes

| Volume | Function |
| :---: | --- |
| `/config` | Config file location. `config.yml` must be placed here. |
| `/sonarr_root` | Root media directory as seen by this container. Must match Sonarr's library path. |
| `/logs` | Log file output. |
| `/staging` | Optional. Staging directory for downloads before Sonarr import. See below. |

### Environment Variables

| Variable | Function |
| :---: | --- |
| `PUID` | User ID to run as. Should match your host user. |
| `PGID` | Group ID to run as. Should match your host group. |

## Configuration

On first run a `config.yml.template` is created in `/config`. Copy it to `config.yml` and edit accordingly.

Full reference: [config.yml.template](./app/config.yml.template)

### Minimal config

```yaml
sonarrytdl:
  scan_interval: 60

sonarr:
  host: 192.168.1.123
  port: 8989
  apikey: your_api_key
  ssl: false
  version: v4
  localpath: /sonarr_root

ytdl:
  default_format: bestvideo[width<=1920]+bestaudio/best[width<=1920]

series:
  - title: Smarter Every Day
    url: https://www.youtube.com/channel/UC6107grRI4m0o2-emgoDnAA
```

### Path mapping

If Sonarr and this container see the media library at different paths, set both `path` and `localpath`:

```yaml
sonarr:
  path: /mnt/library/tvshows     # path as Sonarr sees it
  localpath: /sonarr_root        # path as this container sees it
```

## Staging

By default files are downloaded directly to the library. Enabling staging downloads to a separate directory first and notifies Sonarr via `DownloadedEpisodesScan`, which creates a proper history entry in Sonarr.

To enable, mount the staging directory in both this container and Sonarr, then set `staging_path` to the path Sonarr sees:

```yaml
# docker-compose - sonarr_youtubedl service
- ${DATADIR}/downloads/sonarr_youtubedl:/staging

# docker-compose - sonarr service
- ${DATADIR}/downloads/sonarr_youtubedl:/staging  # or its equivalent host path
```

```yaml
# config.yml
sonarr:
  staging_path: /mnt/library/downloads/sonarr_youtubedl
```

If `staging_path` is not set or `/staging` is not writable, staging is automatically disabled and downloads go directly to the library.

## Telegram Notifications

Optional notifications on download start and/or completion. Uses an existing Telegram bot.

```yaml
telegram:
  bot_token: your_bot_token   # from @BotFather
  chat_id: your_chat_id       # your user or group chat ID
  notify_on:
    - download_start
    - download_complete
```

To find your `chat_id`, message your bot then visit:
`api.telegram.org/bot<your_token>/getUpdates`

## Webhook Notifications

Optional outbound webhook on download events. Sends a JSON payload to any HTTP endpoint - compatible with Discord, Home Assistant, n8n, Zapier, or anything that accepts a webhook.

```yaml
webhook:
  url: https://your-endpoint.com/hook
  notify_on:
    - download_start
    - download_complete
```

The payload looks like:

```json
{
  "event": "download_complete",
  "series": "Ms Rachel - Songs for Littles",
  "episode": "S05E06",
  "title": "Counting numbers",
  "timestamp": "2026-03-21T12:00:00+00:00"
}
```

Telegram and webhook can be used simultaneously or independently.

## Rate Limiting

If YouTube rate limits a download, the script automatically sleeps and retries with exponential backoff. No configuration is required - sensible defaults are used out of the box.

To tune the behaviour, add these optional values under `sonarrytdl`:

```yaml
sonarrytdl:
  rate_limit_sleep: 900     # base sleep in seconds on first rate limit hit (default 15 minutes)
  backoff_multiplier: 2.0   # multiplier applied on each subsequent hit (default doubles each time)
  backoff_max: 3600         # maximum sleep cap in seconds (default 1 hour)
```

With the defaults, consecutive hits sleep for 15m → 30m → 60m → 60m (capped). The counter resets automatically after a successful download.

## Series options

| Option | Description |
| :---: | --- |
| `url` | YouTube channel, playlist, or video URL |
| `cookies_file` | Filename of a cookies.txt in `/config`, for authenticated downloads |
| `format` | yt-dlp format string, overrides global `default_format` |
| `playlistreverse` | Set to `False` to process playlist in forward order. Default `True`. |
| `min_check_interval` | Minimum minutes between yt-dlp scans for this series. Sonarr is still polled every `scan_interval`. |
| `offset` | Time offset for pre-release episodes e.g. `days: 2, hours: 3` |
| `subtitles` | Download and embed subtitles. See template for options. |
| `extra_args` | Per-series yt-dlp options, merged over global `extra_args`. Series values take priority. |
| `regex.sonarr` | Regex match/replace applied to the Sonarr episode title before matching |
| `regex.site` | Regex match/replace applied to the YouTube search term independently |

## Notes on title matching

This script matches Sonarr episode titles against YouTube video titles. The TVDB (Sonarr's metadata source) and YouTube don't always agree on episode titles. A regex pre-filter is applied first - if nothing matches, fuzzy matching runs across the full playlist as fallback. Both happen in a single API call.

If a series consistently fails to match, use `regex.sonarr` to clean up the Sonarr title:

```yaml
regex:
  sonarr:
    match: ' PT \d+'
    replace: ''
```

## Per-series yt-dlp options

Any yt-dlp option can be set per-series under `extra_args`, overriding the global value for that series only. Useful for limiting playlist scans on large channels or enabling SponsorBlock on specific series:

```yaml
series:
  - title: Ms Rachel - Songs for Littles
    url: https://www.youtube.com/channel/UCG2CL6EUjG8TVT1Tpl9nJdg/videos
    extra_args:
      playlistend: 20                                      # only scan 20 most recent videos
      sponsorblock_remove: sponsor,selfpromo,interaction   # remove sponsor segments
```

See the [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp) for all available options.
