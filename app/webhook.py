import logging
from datetime import datetime, timezone
import requests

logger = logging.getLogger('sonarr_youtubedl')


class Webhook:

    def __init__(self, cfg):
        webhook = cfg.get('webhook', {})
        self.url = webhook.get('url', '')
        self.notify_on = webhook.get('notify_on', [])
        self.enabled = bool(self.url)

        if self.enabled:
            logger.info(f"Webhook notifications enabled for: {', '.join(self.notify_on) or 'none'}")

    def _send(self, event, series_title, episode_number, episode_title):
        payload = {
            'event': event,
            'series': series_title,
            'episode': episode_number,
            'title': episode_title,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        try:
            response = requests.post(self.url, json=payload, timeout=10)
            if not response.ok:
                logger.warning(f"Webhook failed: {response.status_code} {response.text}")
        except Exception as e:
            logger.warning(f"Webhook error: {e}")

    def notify_download_start(self, series_title, episode_number, episode_title):
        if self.enabled and 'download_start' in self.notify_on:
            self._send('download_start', series_title, episode_number, episode_title)

    def notify_download_complete(self, series_title, episode_number, episode_title):
        if self.enabled and 'download_complete' in self.notify_on:
            self._send('download_complete', series_title, episode_number, episode_title)