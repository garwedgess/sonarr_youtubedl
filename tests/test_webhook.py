import os
import sys
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault('CONFIGPATH', '/config/config.yml')
sys.path.insert(0, os.path.dirname(__file__))

from webhook import Webhook


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_webhook(notify_on=None, url='https://example.com/hook'):
    return Webhook({'webhook': {
        'url': url,
        'notify_on': notify_on or ['download_start', 'download_complete'],
    }})


# ---------------------------------------------------------------------------
# TestWebhookInit
# ---------------------------------------------------------------------------

class TestWebhookInit:

    def test_disabled_with_no_config(self):
        w = Webhook({})
        assert w.enabled is False

    def test_disabled_with_empty_webhook(self):
        w = Webhook({'webhook': {}})
        assert w.enabled is False

    def test_enabled_with_url(self):
        w = Webhook({'webhook': {'url': 'https://example.com/hook'}})
        assert w.enabled is True

    def test_notify_on_defaults_to_empty(self):
        w = Webhook({})
        assert w.notify_on == []

    def test_notify_on_set_from_config(self):
        w = make_webhook(notify_on=['download_start', 'download_complete'])
        assert 'download_start' in w.notify_on
        assert 'download_complete' in w.notify_on


# ---------------------------------------------------------------------------
# TestWebhookSend
# ---------------------------------------------------------------------------

class TestWebhookSend:

    def test_send_posts_to_configured_url(self):
        w = make_webhook()
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w._send('download_start', 'Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.call_args.args[0] == 'https://example.com/hook'

    def test_payload_contains_event(self):
        w = make_webhook()
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w._send('download_start', 'Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.call_args.kwargs['json']['event'] == 'download_start'

    def test_payload_contains_series(self):
        w = make_webhook()
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w._send('download_start', 'Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.call_args.kwargs['json']['series'] == 'Ms Rachel'

    def test_payload_contains_episode_number(self):
        w = make_webhook()
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w._send('download_start', 'Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.call_args.kwargs['json']['episode'] == 'S01E01'

    def test_payload_contains_title(self):
        w = make_webhook()
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w._send('download_start', 'Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.call_args.kwargs['json']['title'] == 'Colours'

    def test_payload_contains_timestamp(self):
        w = make_webhook()
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w._send('download_start', 'Ms Rachel', 'S01E01', 'Colours')
        assert 'timestamp' in mock_post.call_args.kwargs['json']

    def test_send_uses_timeout(self):
        w = make_webhook()
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w._send('download_start', 'Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.call_args.kwargs['timeout'] == 10

    def test_failed_response_logs_warning(self):
        w = make_webhook()
        with patch('webhook.requests.post') as mock_post, \
             patch('webhook.logger') as mock_log:
            mock_post.return_value = MagicMock(ok=False, status_code=500, text='Server Error')
            w._send('download_start', 'Ms Rachel', 'S01E01', 'Colours')
        mock_log.warning.assert_called_once()
        assert '500' in str(mock_log.warning.call_args)

    def test_exception_logs_warning(self):
        w = make_webhook()
        with patch('webhook.requests.post', side_effect=Exception('connection refused')), \
             patch('webhook.logger') as mock_log:
            w._send('download_start', 'Ms Rachel', 'S01E01', 'Colours')
        mock_log.warning.assert_called_once()
        assert 'connection refused' in str(mock_log.warning.call_args)


# ---------------------------------------------------------------------------
# TestNotifyDownloadStart
# ---------------------------------------------------------------------------

class TestWebhookNotifyDownloadStart:

    def test_sends_when_enabled_and_in_notify_on(self):
        w = make_webhook(notify_on=['download_start'])
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w.notify_download_start('Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.called

    def test_event_is_download_start(self):
        w = make_webhook(notify_on=['download_start'])
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w.notify_download_start('Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.call_args.kwargs['json']['event'] == 'download_start'

    def test_not_sent_when_disabled(self):
        w = Webhook({})
        with patch('webhook.requests.post') as mock_post:
            w.notify_download_start('Ms Rachel', 'S01E01', 'Colours')
        assert not mock_post.called

    def test_not_sent_when_not_in_notify_on(self):
        w = make_webhook(notify_on=['download_complete'])
        with patch('webhook.requests.post') as mock_post:
            w.notify_download_start('Ms Rachel', 'S01E01', 'Colours')
        assert not mock_post.called


# ---------------------------------------------------------------------------
# TestNotifyDownloadComplete
# ---------------------------------------------------------------------------

class TestWebhookNotifyDownloadComplete:

    def test_sends_when_enabled_and_in_notify_on(self):
        w = make_webhook(notify_on=['download_complete'])
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w.notify_download_complete('Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.called

    def test_event_is_download_complete(self):
        w = make_webhook(notify_on=['download_complete'])
        with patch('webhook.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            w.notify_download_complete('Ms Rachel', 'S01E01', 'Colours')
        assert mock_post.call_args.kwargs['json']['event'] == 'download_complete'

    def test_not_sent_when_disabled(self):
        w = Webhook({})
        with patch('webhook.requests.post') as mock_post:
            w.notify_download_complete('Ms Rachel', 'S01E01', 'Colours')
        assert not mock_post.called

    def test_not_sent_when_not_in_notify_on(self):
        w = make_webhook(notify_on=['download_start'])
        with patch('webhook.requests.post') as mock_post:
            w.notify_download_complete('Ms Rachel', 'S01E01', 'Colours')
        assert not mock_post.called