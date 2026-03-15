# sonarr_youtubedl by [@garwedgess](https://github.com/garwedgess)

> Originally forked from [@whatdaybob](https://github.com/whatdaybob/sonarr_youtubedl)

[sonarr_youtubedl](https://github.com/garwedgess/sonarr_youtubedl) is a [Sonarr](https://sonarr.tv/) companion script to allow automatic downloading of web series normally unavailable to Sonarr. Using [yt-dlp](https://github.com/yt-dlp/yt-dlp) it downloads from any of the [supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) and imports directly into your Sonarr library.

## Features

- Automatic downloading of web series from YouTube and other supported sites
- Imports via Sonarr's `DownloadedEpisodesScan` for proper history entries
- Fuzzy title matching with regex pre-filter - handles title mismatches between TVDB and YouTube
- PO token support via [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) for authenticated YouTube access
- Telegram notifications on download start and completion
- Per-series configuration: custom format, cookies, subtitles, time offsets, regex title cleanup, scan intervals
- Duplicate file protection - skips downloads if file already exists in library or staging
- Optional staging directory for clean separation between downloads and media library

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
| x86-64 | dev |

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
      - /path/to/media/sonarr_youtubedl_staging:/staging  # optional, see Staging below
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
- ${DATADIR}/sonarr_youtubedl_staging:/staging

# docker-compose - sonarr service
- ${DATADIR}/sonarr_youtubedl_staging:/staging  # or its equivalent host path
```

```yaml
# config.yml
sonarr:
  staging_path: /mnt/library/sonarr_youtubedl_staging
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
`https://api.telegram.org/bot<your_token>/getUpdates`

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