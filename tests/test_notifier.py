import pytest
from unittest.mock import patch, MagicMock

from notifier import Notifier


# ---------------------------------------------------------------------------
# TestNotifierInit
# ---------------------------------------------------------------------------

class TestNotifierInit:

    def test_disabled_with_no_config(self):
        n = Notifier({})
        assert n.enabled is False

    def test_disabled_with_empty_telegram(self):
        n = Notifier({'telegram': {}})
        assert n.enabled is False

    def test_disabled_with_token_only(self):
        n = Notifier({'telegram': {'bot_token': 'abc123'}})
        assert n.enabled is False

    def test_disabled_with_chat_id_only(self):
        n = Notifier({'telegram': {'chat_id': '123'}})
        assert n.enabled is False

    def test_enabled_with_token_and_chat_id(self):
        n = Notifier({'telegram': {'bot_token': 'abc123', 'chat_id': '123'}})
        assert n.enabled is True

    def test_notify_on_defaults_to_empty(self):
        n = Notifier({})
        assert n.notify_on == []

    def test_notify_on_set_from_config(self):
        n = Notifier({'telegram': {'bot_token': 'abc', 'chat_id': '123', 'notify_on': ['download_start', 'download_complete']}})
        assert 'download_start' in n.notify_on
        assert 'download_complete' in n.notify_on


# ---------------------------------------------------------------------------
# TestNotifierSend
# ---------------------------------------------------------------------------

class TestNotifierSend:

    def _enabled(self, notify_on=None):
        return Notifier({'telegram': {
            'bot_token': 'testtoken',
            'chat_id': '12345',
            'notify_on': notify_on or ['download_start', 'download_complete'],
        }})

    def test_send_posts_to_correct_url(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n._send('test message')
        url = mock_post.call_args.args[0]
        assert 'testtoken' in url
        assert 'api.telegram.org' in url

    def test_send_includes_chat_id(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n._send('test message')
        call_json = mock_post.call_args.kwargs['json']
        assert call_json['chat_id'] == '12345'

    def test_send_includes_message_text(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n._send('hello world')
        assert mock_post.call_args.kwargs['json']['text'] == 'hello world'

    def test_send_uses_html_parse_mode(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n._send('test')
        assert mock_post.call_args.kwargs['json']['parse_mode'] == 'HTML'

    def test_failed_response_logs_warning(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post, \
             patch('notifier.logger') as mock_log:
            mock_post.return_value = MagicMock(ok=False, status_code=401, text='Unauthorized')
            n._send('test')
        mock_log.warning.assert_called_once()
        assert '401' in str(mock_log.warning.call_args)

    def test_exception_logs_warning(self):
        n = self._enabled()
        with patch('notifier.requests.post', side_effect=Exception('connection timeout')), \
             patch('notifier.logger') as mock_log:
            n._send('test')
        mock_log.warning.assert_called_once()
        assert 'connection timeout' in str(mock_log.warning.call_args)

    def test_send_uses_timeout(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n._send('test')
        assert mock_post.call_args.kwargs['timeout'] == 10


# ---------------------------------------------------------------------------
# TestNotifyDownloadStart
# ---------------------------------------------------------------------------

class TestNotifyDownloadStart:

    def _enabled(self, notify_on=None):
        return Notifier({'telegram': {
            'bot_token': 'testtoken',
            'chat_id': '12345',
            'notify_on': notify_on or ['download_start'],
        }})

    def test_sends_when_enabled_and_in_notify_on(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n.notify_download_start('Ms Rachel', 'Colours and Shapes')
        assert mock_post.called

    def test_message_contains_series_title(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n.notify_download_start('Ms Rachel', 'Colours and Shapes')
        assert 'Ms Rachel' in mock_post.call_args.kwargs['json']['text']

    def test_message_contains_episode_title(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n.notify_download_start('Ms Rachel', 'Colours and Shapes')
        assert 'Colours and Shapes' in mock_post.call_args.kwargs['json']['text']

    def test_message_contains_downloading_indicator(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n.notify_download_start('Ms Rachel', 'Colours and Shapes')
        assert 'Downloading' in mock_post.call_args.kwargs['json']['text']

    def test_not_sent_when_disabled(self):
        n = Notifier({})
        with patch('notifier.requests.post') as mock_post:
            n.notify_download_start('Ms Rachel', 'Colours')
        assert not mock_post.called

    def test_not_sent_when_not_in_notify_on(self):
        n = self._enabled(notify_on=['download_complete'])
        with patch('notifier.requests.post') as mock_post:
            n.notify_download_start('Ms Rachel', 'Colours')
        assert not mock_post.called


# ---------------------------------------------------------------------------
# TestNotifyDownloadComplete
# ---------------------------------------------------------------------------

class TestNotifyDownloadComplete:

    def _enabled(self, notify_on=None):
        return Notifier({'telegram': {
            'bot_token': 'testtoken',
            'chat_id': '12345',
            'notify_on': notify_on or ['download_complete'],
        }})

    def test_sends_when_enabled_and_in_notify_on(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n.notify_download_complete('Ms Rachel', 'Colours and Shapes')
        assert mock_post.called

    def test_message_contains_series_title(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n.notify_download_complete('Ms Rachel', 'Colours and Shapes')
        assert 'Ms Rachel' in mock_post.call_args.kwargs['json']['text']

    def test_message_contains_episode_title(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n.notify_download_complete('Ms Rachel', 'Colours and Shapes')
        assert 'Colours and Shapes' in mock_post.call_args.kwargs['json']['text']

    def test_message_contains_downloaded_indicator(self):
        n = self._enabled()
        with patch('notifier.requests.post') as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            n.notify_download_complete('Ms Rachel', 'Colours and Shapes')
        assert 'Downloaded' in mock_post.call_args.kwargs['json']['text']

    def test_not_sent_when_disabled(self):
        n = Notifier({})
        with patch('notifier.requests.post') as mock_post:
            n.notify_download_complete('Ms Rachel', 'Colours')
        assert not mock_post.called

    def test_not_sent_when_not_in_notify_on(self):
        n = self._enabled(notify_on=['download_start'])
        with patch('notifier.requests.post') as mock_post:
            n.notify_download_complete('Ms Rachel', 'Colours')
        assert not mock_post.called