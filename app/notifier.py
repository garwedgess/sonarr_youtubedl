import logging
import requests

logger = logging.getLogger('sonarr_youtubedl')

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class Notifier:

    def __init__(self, cfg):
        telegram = cfg.get('telegram', {})
        self.bot_token = telegram.get('bot_token', '')
        self.chat_id = telegram.get('chat_id', '')
        self.notify_on = telegram.get('notify_on', [])
        self.enabled = bool(self.bot_token and self.chat_id)

        if self.enabled:
            logger.info(f"Telegram notifications enabled for: {', '.join(self.notify_on) or 'none'}")

    def _send(self, message):
        try:
            response = requests.post(
                TELEGRAM_API.format(token=self.bot_token),
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10
            )
            if not response.ok:
                logger.warning(f"Telegram notification failed: {response.status_code} {response.text}")
        except Exception as e:
            logger.warning(f"Telegram notification error: {e}")

    def notify_download_start(self, series_title, episode_title):
        if self.enabled and 'download_start' in self.notify_on:
            self._send(f"⬇️ <b>Downloading</b>\n{series_title}\n{episode_title}")

    def notify_download_complete(self, series_title, episode_title):
        if self.enabled and 'download_complete' in self.notify_on:
            self._send(f"✅ <b>Downloaded</b>\n{series_title}\n{episode_title}")