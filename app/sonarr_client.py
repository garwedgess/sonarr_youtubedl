import logging
import urllib.parse
import requests

logger = logging.getLogger('sonarr_youtubedl')


class SonarrClient:

    def __init__(self, base_url, api_version, api_key):
        self.base_url = base_url
        self.api_version = api_version
        self.api_key = api_key

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}/{self.api_version}/{endpoint}"
        logger.debug(f"GET {url}")
        default_params = {"apikey": self.api_key}
        if params:
            default_params.update(params)
        return requests.get(
            f"{url}?{urllib.parse.urlencode(default_params)}",
            timeout=30
        ).json()

    def _post(self, endpoint, data):
        url = f"{self.base_url}/{self.api_version}/{endpoint}"
        logger.debug(f"POST {url}")
        return requests.post(
            url,
            headers={"Content-Type": "application/json"},
            params=(("apikey", self.api_key),),
            json=data,
            timeout=30
        ).json()

    def get_series(self):
        return self._get("series")

    def get_episodes(self, series_id):
        return self._get("episode", {"seriesId": series_id})

    def get_quality_profile(self, profile_id):
        return self._get(f"qualityprofile/{profile_id}")

    def get_naming_config(self):
        return self._get("config/naming")

    def refresh(self, series_id):
        return self._post("command", {"name": "RefreshSeries", "seriesId": str(series_id)})

    def rescan(self, series_id):
        return self._post("command", {"name": "RescanSeries", "seriesId": str(series_id)})

    def get_health(self):
        return self._get("health")

    def downloaded_episodes_scan(self, path):
        return self._post("command", {
            "name": "DownloadedEpisodesScan",
            "path": path,
            "importMode": "Move"
        })