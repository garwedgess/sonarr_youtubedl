import copy
import datetime
import os
import sys
import types
import pytest
from unittest.mock import patch, MagicMock, call

os.environ.setdefault('CONFIGPATH', '/config/config.yml')

# Stub modules not available in CI test environment
for _stub in ['yt_dlp', 'schedule']:
    if _stub not in sys.modules:
        sys.modules[_stub] = MagicMock()

# ---------------------------------------------------------------------------
# Stub out modules that require Docker/yt-dlp/network at import time
# ---------------------------------------------------------------------------

# Use real modules so their test files are not polluted
import notifier as _notifier_module
import staging_manager as _staging_module
import downloader as _downloader_module
import sonarr_client as _sonarr_client_module
sys.modules['notifier'] = _notifier_module
sys.modules['staging_manager'] = _staging_module
sys.modules['downloader'] = _downloader_module
sys.modules['sonarr_client'] = _sonarr_client_module

from sonarr_youtubedl import SonarrYTDL

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

CFG = {
    'sonarrytdl': {
        'scan_interval': '60',
        'debug': 'false',
        'rate_limit_sleep': '900',
        'backoff_multiplier': '2.0',
        'backoff_max': '3600',
    },
    'sonarr': {
        'host': 'localhost',
        'port': '8989',
        'ssl': 'false',
        'apikey': 'testkey123',
        'version': 'v4',
    },
    'ytdl': {
        'default_format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mkv',
    },
    'series': [
        {'title': 'Ms Rachel', 'url': 'https://youtube.com/channel/msrachel'},
    ],
    'telegram': {},
}

NAMING = {
    'seasonFolderFormat': 'Season {season:2}',
    'numberStyle': 'S{season:2}E{episode:2}',
}

SONARR_SERIES = [
    {'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel', 'monitored': True, 'qualityProfileId': 5},
    {'id': 2, 'title': 'Peppa Pig', 'path': '/tv/Peppa Pig', 'monitored': True, 'qualityProfileId': 5},
]

QUALITY_PROFILE = {
    'items': [{'allowed': True, 'quality': {'resolution': 1080}}]
}

NOW = datetime.datetime(2024, 6, 1, 12, 0, 0)

EPISODE_BASE = {
    'seriesId': 1,
    'monitored': True,
    'hasFile': False,
    'airDateUtc': '2024-05-01T12:00:00Z',
    'seasonNumber': 1,
    'episodeNumber': 1,
    'qualityProfileId': 5,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_sonarr_client(series=None, episodes=None, naming=None):
    """Return a mock SonarrClient with sensible defaults."""
    mock = MagicMock()
    mock.get_naming_config.return_value = naming or NAMING
    mock.get_series.return_value = copy.deepcopy(series if series is not None else SONARR_SERIES)
    mock.get_episodes.return_value = copy.deepcopy(episodes if episodes is not None else [])
    mock.get_quality_profile.return_value = QUALITY_PROFILE
    return mock


def make_client(cfg=None, series=None, episodes=None):
    """Construct a SonarrYTDL instance with mocked dependencies."""
    mock_sonarr = make_sonarr_client(series=series, episodes=episodes)
    with patch('sonarr_youtubedl.load_config', return_value=cfg or CFG), \
         patch('sonarr_youtubedl.validate_config'), \
         patch('sonarr_youtubedl.SonarrClient', return_value=mock_sonarr), \
         patch.object(mock_sonarr, 'get_health', return_value=[]), \
         patch('sonarr_youtubedl.Notifier', return_value=MagicMock()), \
         patch.object(_staging_module, 'is_available', return_value=False), \
         patch.object(_staging_module, 'ensure'), \
         patch.object(_staging_module, 'clean'), \
         patch.object(_staging_module, 'find_file', return_value=None), \
         patch.object(_staging_module, 'staging_path', return_value='/staging/test.%(ext)s'), \
         patch.object(_staging_module, 'notify_sonarr', return_value=True), \
         patch.object(_downloader_module, 'search', return_value=None), \
         patch.object(_downloader_module, 'download', return_value=True):
        client = SonarrYTDL()
    client.sonarr = mock_sonarr
    return client, mock_sonarr


def make_episode(**kwargs):
    """Return an episode dict with defaults overridden by kwargs."""
    ep = dict(EPISODE_BASE)
    ep.update(kwargs)
    return ep


# ---------------------------------------------------------------------------
# TestCheckSonarrConnection
# ---------------------------------------------------------------------------

class TestCheckSonarrConnection:

    def test_logs_ok_when_healthy(self):
        client, mock_sonarr = make_client()
        mock_sonarr.get_health.return_value = []
        with patch.object(client, 'client', mock_sonarr),              patch('sonarr_youtubedl.logger') as mock_log:
            client._check_sonarr_connection()
        assert any('OK' in str(c) for c in mock_log.info.call_args_list)

    def test_logs_warning_for_each_issue(self):
        client, mock_sonarr = make_client()
        issues = [
            {'type': 'warning', 'message': 'Indexer unavailable'},
            {'type': 'error', 'message': 'Disk space low'},
        ]
        mock_sonarr.get_health.return_value = issues
        with patch.object(client, 'client', mock_sonarr),              patch('sonarr_youtubedl.logger') as mock_log:
            client._check_sonarr_connection()
        assert mock_log.warning.call_count == 2

    def test_exits_when_sonarr_unreachable(self):
        client, mock_sonarr = make_client()
        mock_sonarr.get_health.side_effect = Exception('Connection refused')
        with patch.object(client, 'client', mock_sonarr),              pytest.raises(SystemExit):
            client._check_sonarr_connection()

    def test_continues_when_sonarr_has_warnings(self):
        client, mock_sonarr = make_client()
        mock_sonarr.get_health.return_value = [{'type': 'warning', 'message': 'Indexer unavailable'}]
        with patch.object(client, 'client', mock_sonarr):
            client._check_sonarr_connection()  # should not raise


# ---------------------------------------------------------------------------
# TestFilterseries
# ---------------------------------------------------------------------------



class TestFilterseries:

    def test_returns_only_configured_series(self):
        client, mock_sonarr = make_client()
        result = client.filterseries()
        assert len(result) == 1
        assert result[0]['title'] == 'Ms Rachel'

    def test_series_not_in_config_excluded(self):
        client, mock_sonarr = make_client()
        result = client.filterseries()
        titles = [s['title'] for s in result]
        assert 'Peppa Pig' not in titles

    def test_url_set_from_config(self):
        client, mock_sonarr = make_client()
        result = client.filterseries()
        assert result[0]['url'] == 'https://youtube.com/channel/msrachel'

    def test_playlistreverse_defaults_true(self):
        client, mock_sonarr = make_client()
        result = client.filterseries()
        assert result[0]['playlistreverse'] is True

    def test_playlistreverse_false_from_config(self):
        cfg = {**CFG, 'series': [{'title': 'Ms Rachel', 'url': 'https://youtube.com/channel/msrachel', 'playlistreverse': 'False'}]}
        client, mock_sonarr = make_client(cfg=cfg)
        result = client.filterseries()
        assert result[0]['playlistreverse'] is False

    def test_unmonitored_series_still_returned(self):
        series = [{'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel', 'monitored': False, 'qualityProfileId': 5}]
        client, mock_sonarr = make_client(series=series)
        result = client.filterseries()
        assert len(result) == 1

    def test_cookies_file_set_when_exists(self, tmp_path):
        cookie_file = tmp_path / 'cookies.txt'
        cookie_file.write_text('cookie data')
        cfg = {**CFG, 'series': [{'title': 'Ms Rachel', 'url': 'https://youtube.com/channel/msrachel', 'cookies_file': 'cookies.txt'}]}
        with patch('sonarr_youtubedl.CONFIGPATH', str(tmp_path) + os.sep):
            client, _ = make_client(cfg=cfg)
            result = client.filterseries()
        assert result[0]['cookies_file'] == str(cookie_file)

    def test_cookies_file_none_when_missing(self):
        cfg = {**CFG, 'series': [{'title': 'Ms Rachel', 'url': 'https://youtube.com/channel/msrachel', 'cookies_file': 'nonexistent.txt'}]}
        client, _ = make_client(cfg=cfg)
        result = client.filterseries()
        assert result[0]['cookies_file'] is None

    def test_sonarr_regex_set_from_config(self):
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
            'regex': {'sonarr': {'match': r'^Ms Rachel - ', 'replace': ''}}
        }]}
        client, _ = make_client(cfg=cfg)
        result = client.filterseries()
        assert result[0]['sonarr_regex'] == {'match': r'^Ms Rachel - ', 'replace': ''}

    def test_offset_set_from_config(self):
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
            'offset': {'days': '3'}
        }]}
        client, _ = make_client(cfg=cfg)
        result = client.filterseries()
        assert result[0]['offset'] == {'days': '3'}

    def test_empty_sonarr_response_returns_empty(self):
        # Sonarr returns no series at all
        client, mock_sonarr = make_client(series=[])
        mock_sonarr.get_series.return_value = []
        result = client.filterseries()
        assert result == []


# ---------------------------------------------------------------------------
# TestGetMissingEpisodes
# ---------------------------------------------------------------------------

class TestGetMissingEpisodes:

    def _run(self, episodes, series=None):
        client, mock_sonarr = make_client(episodes=episodes)
        mock_sonarr.get_quality_profile.return_value = QUALITY_PROFILE
        if series is None:
            series = client.filterseries()
        with patch('sonarr_youtubedl.datetime') as mock_dt:
            mock_dt.now.return_value = NOW
            mock_dt.strptime = datetime.datetime.strptime
            return client.get_missing_episodes(series)

    def test_wanted_episode_returned(self):
        eps = [make_episode(id=1, title='Ep1')]
        needed = self._run(eps)
        assert len(needed) == 1
        assert needed[0]['title'] == 'Ep1'

    def test_unmonitored_episode_excluded(self):
        eps = [make_episode(id=1, title='Ep1', monitored=False)]
        needed = self._run(eps)
        assert needed == []

    def test_episode_with_file_excluded(self):
        eps = [make_episode(id=1, title='Ep1', hasFile=True)]
        needed = self._run(eps)
        assert needed == []

    def test_future_episode_excluded(self):
        eps = [make_episode(id=1, title='Ep1', airDateUtc='2024-07-01T12:00:00Z')]
        needed = self._run(eps)
        assert needed == []

    def test_past_episode_included(self):
        eps = [make_episode(id=1, title='Ep1', airDateUtc='2024-01-01T12:00:00Z')]
        needed = self._run(eps)
        assert len(needed) == 1

    def test_multiple_episodes_filtered_correctly(self):
        eps = [
            make_episode(id=1, title='Ep1'),                                           # wanted
            make_episode(id=2, title='Ep2', monitored=False),                          # unmonitored
            make_episode(id=3, title='Ep3', hasFile=True),                             # has file
            make_episode(id=4, title='Ep4', airDateUtc='2024-07-01T12:00:00Z'),        # future
        ]
        needed = self._run(eps)
        assert len(needed) == 1
        assert needed[0]['title'] == 'Ep1'

    def test_sonarr_regex_applied_to_title(self):
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
            'regex': {'sonarr': {'match': r'^Ms Rachel - ', 'replace': ''}}
        }]}
        client, mock_sonarr = make_client(cfg=cfg)
        mock_sonarr.get_episodes.return_value = [make_episode(id=1, title='Ms Rachel - Colours')]
        mock_sonarr.get_quality_profile.return_value = QUALITY_PROFILE
        series = client.filterseries()
        with patch('sonarr_youtubedl.datetime') as mock_dt:
            mock_dt.now.return_value = NOW
            mock_dt.strptime = datetime.datetime.strptime
            needed = client.get_missing_episodes(series)
        assert needed[0]['title'] == 'Colours'

    def test_offset_shifts_air_date(self):
        # Episode airs 2024-06-02, offset +2 days makes it 2024-06-04, still past NOW (2024-06-01)
        # Without offset it would be included, with +30 days offset it becomes future
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
            'offset': {'days': '30'}
        }]}
        client, mock_sonarr = make_client(cfg=cfg)
        mock_sonarr.get_episodes.return_value = [make_episode(id=1, title='Ep1', airDateUtc='2024-05-20T12:00:00Z')]
        mock_sonarr.get_quality_profile.return_value = QUALITY_PROFILE
        series = client.filterseries()
        with patch('sonarr_youtubedl.datetime') as mock_dt:
            mock_dt.now.return_value = NOW
            mock_dt.strptime = datetime.datetime.strptime
            needed = client.get_missing_episodes(series)
        assert needed == []

    def test_series_removed_when_no_episodes_needed(self):
        eps = [make_episode(id=1, title='Ep1', hasFile=True)]
        client, mock_sonarr = make_client(episodes=eps)
        mock_sonarr.get_quality_profile.return_value = QUALITY_PROFILE
        series = client.filterseries()
        with patch('sonarr_youtubedl.datetime') as mock_dt:
            mock_dt.now.return_value = NOW
            mock_dt.strptime = datetime.datetime.strptime
            client.get_missing_episodes(series)
        assert series == []


# ---------------------------------------------------------------------------
# TestDownloadEpisode
# ---------------------------------------------------------------------------

class TestDownloadEpisode:

    def _make(self):
        client, mock_sonarr = make_client()
        client.quality_map = {5: 'bestvideo[width<=1920]+bestaudio/best'}
        return client, mock_sonarr

    def _ser(self, **kwargs):
        s = {
            'id': 1,
            'title': 'Ms Rachel',
            'path': '/tv/Ms Rachel',
            'qualityProfileId': 5,
            'url': 'https://youtube.com/channel/msrachel',
            'playlistreverse': True,
            'cookies_file': None,
            'subtitles': None,
        }
        s.update(kwargs)
        return s

    def _eps(self, **kwargs):
        e = {'id': 1, 'seriesId': 1, 'title': 'Colours and Shapes', 'seasonNumber': 1, 'episodeNumber': 1}
        e.update(kwargs)
        return e

    def test_no_url_found_returns_false(self):
        client, _ = self._make()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False):
            mock_dl.search.return_value = None
            result = client._download_episode(self._ser(), self._eps())
        assert result is False

    def test_successful_download_returns_true(self):
        client, mock_sonarr = self._make()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.return_value = True
            result = client._download_episode(self._ser(), self._eps())
        assert result is True

    def test_successful_download_triggers_rescan(self):
        client, mock_sonarr = self._make()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.return_value = True
            client._download_episode(self._ser(), self._eps())
        mock_sonarr.refresh.assert_called_once_with(1)
        mock_sonarr.rescan.assert_called_once_with(1)

    def test_library_file_exists_triggers_rescan_returns_true(self):
        client, mock_sonarr = self._make()
        with patch.object(client, '_library_file_exists', return_value=True):
            result = client._download_episode(self._ser(), self._eps())
        assert result is True
        mock_sonarr.refresh.assert_called_once()
        mock_sonarr.rescan.assert_called_once()

    def test_per_series_extra_args_override_global(self):
        client, _ = self._make()
        client.ytdl_extra_args = {'playlistend': 20, 'socket_timeout': 30}
        ser = self._ser(extra_args={'playlistend': 5})
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False):
            mock_dl.search.return_value = None
            client._download_episode(ser, self._eps())
        called_args = mock_dl.search.call_args[1]['extra_args']
        assert called_args['playlistend'] == 5
        assert called_args['socket_timeout'] == 30

    def test_global_extra_args_used_when_no_series_override(self):
        client, _ = self._make()
        client.ytdl_extra_args = {'socket_timeout': 30}
        ser = self._ser()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False):
            mock_dl.search.return_value = None
            client._download_episode(ser, self._eps())
        called_args = mock_dl.search.call_args[1]['extra_args']
        assert called_args['socket_timeout'] == 30

    def test_merged_extra_args_passed_to_download(self):
        client, mock_sonarr = self._make()
        client.ytdl_extra_args = {'socket_timeout': 30}
        ser = self._ser(extra_args={'playlistend': 5})
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.return_value = True
            client._download_episode(ser, self._eps())
        called_args = mock_dl.download.call_args[1]['extra_args']
        assert called_args['playlistend'] == 5
        assert called_args['socket_timeout'] == 30

    def test_download_failure_returns_false(self):
        client, _ = self._make()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.return_value = False
            result = client._download_episode(self._ser(), self._eps())
        assert result is False

    def test_rate_limit_error_increments_count(self):
        client, _ = self._make()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.side_effect = Exception('HTTP 429: rate-limited')
            client._download_episode(self._ser(), self._eps())
        assert client.rate_limit_count == 1

    def test_rate_limit_error_sleeps(self):
        client, _ = self._make()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep') as mock_sleep:
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.side_effect = Exception('HTTP 429: rate-limited')
            client._download_episode(self._ser(), self._eps())
        mock_sleep.assert_called_once_with(900)

    def test_rate_limit_backoff_increases_on_second_hit(self):
        client, _ = self._make()
        client.rate_limit_count = 1  # simulate prior hit
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep') as mock_sleep:
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.side_effect = Exception('rate limit exceeded')
            client._download_episode(self._ser(), self._eps())
        mock_sleep.assert_called_once_with(1800)

    def test_successful_download_resets_backoff(self):
        client, _ = self._make()
        client.rate_limit_count = 3
        client.current_backoff = 3600
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.return_value = True
            client._download_episode(self._ser(), self._eps())
        assert client.rate_limit_count == 0
        assert client.current_backoff == 900

    def test_non_rate_limit_error_does_not_sleep(self):
        client, _ = self._make()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep') as mock_sleep:
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.side_effect = Exception('Video unavailable')
            client._download_episode(self._ser(), self._eps())
        mock_sleep.assert_not_called()

    def test_non_rate_limit_error_does_not_increment_count(self):
        client, _ = self._make()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.side_effect = Exception('Video unavailable')
            client._download_episode(self._ser(), self._eps())
        assert client.rate_limit_count == 0

    def test_site_regex_applied_before_search(self):
        client, _ = self._make()
        ser = self._ser(site_regex={'match': r'^Ms Rachel - ', 'replace': ''})
        eps = self._eps(title='Ms Rachel - Colours')
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = None
            client._download_episode(ser, eps)
        # Verify search was called with the transformed title
        call_kwargs = mock_dl.search.call_args
        assert call_kwargs.kwargs['episode_title'] == 'Colours'


# ---------------------------------------------------------------------------
# TestDownload (min_check_interval)
# ---------------------------------------------------------------------------

class TestDownload:

    def test_min_check_interval_skips_recent_series(self):
        client, _ = make_client()
        client.quality_map = {5: 'bestvideo+bestaudio/best'}
        ser = {
            'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel',
            'qualityProfileId': 5, 'url': 'https://youtube.com',
            'playlistreverse': True, 'cookies_file': None,
            'subtitles': None, 'min_check_interval': 60,
        }
        eps = [{'id': 1, 'seriesId': 1, 'title': 'Ep1', 'seasonNumber': 1, 'episodeNumber': 1}]

        # Set last_checked to just now so interval hasn't elapsed
        from sonarr_youtubedl import last_checked
        last_checked[1] = datetime.datetime.now()

        with patch.object(client, '_download_episode') as mock_dl_ep:
            client.download([ser], eps)

        mock_dl_ep.assert_not_called()
        # Clean up
        del last_checked[1]

    def test_series_processed_when_interval_elapsed(self):
        client, _ = make_client()
        client.quality_map = {5: 'bestvideo+bestaudio/best'}
        ser = {
            'id': 99, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel',
            'qualityProfileId': 5, 'url': 'https://youtube.com',
            'playlistreverse': True, 'cookies_file': None,
            'subtitles': None, 'min_check_interval': 1,
        }
        eps = [{'id': 1, 'seriesId': 99, 'title': 'Ep1', 'seasonNumber': 1, 'episodeNumber': 1}]

        from sonarr_youtubedl import last_checked
        last_checked[99] = datetime.datetime.now() - datetime.timedelta(minutes=5)

        with patch.object(client, '_download_episode', return_value=True) as mock_dl_ep:
            client.download([ser], eps)

        mock_dl_ep.assert_called_once()
        del last_checked[99]

    def test_nothing_to_process_logs_and_returns(self):
        client, _ = make_client()
        with patch.object(client, '_download_episode') as mock_dl_ep:
            client.download([], [])
        mock_dl_ep.assert_not_called()


# ---------------------------------------------------------------------------
# TestConfigureLogging
# ---------------------------------------------------------------------------

class TestConfigureLogging:

    def test_debug_mode_enabled(self):
        cfg = {**CFG, 'sonarrytdl': {**CFG['sonarrytdl'], 'debug': 'true'}}
        client, _ = make_client(cfg=cfg)
        assert client.debug is True

    def test_debug_mode_disabled_by_default(self):
        client, _ = make_client()
        assert client.debug is False

    def test_low_scan_interval_warning(self):
        cfg = {**CFG, 'sonarrytdl': {**CFG['sonarrytdl'], 'scan_interval': '5'}}
        mock_sonarr = make_sonarr_client()
        with patch('sonarr_youtubedl.load_config', return_value=cfg), \
             patch('sonarr_youtubedl.validate_config'), \
             patch('sonarr_youtubedl.SonarrClient', return_value=mock_sonarr), \
         patch.object(mock_sonarr, 'get_health', return_value=[]), \
             patch('sonarr_youtubedl.Notifier'), \
             patch('sonarr_youtubedl.logger') as mock_log:
            SonarrYTDL()
        warning_calls = [str(c) for c in mock_log.warning.call_args_list]
        assert any('scan_interval' in w for w in warning_calls)

    def test_no_warning_for_normal_scan_interval(self):
        mock_sonarr = make_sonarr_client()
        with patch('sonarr_youtubedl.load_config', return_value=CFG), \
             patch('sonarr_youtubedl.validate_config'), \
             patch('sonarr_youtubedl.SonarrClient', return_value=mock_sonarr), \
         patch.object(mock_sonarr, 'get_health', return_value=[]), \
             patch('sonarr_youtubedl.Notifier'), \
             patch('sonarr_youtubedl.logger') as mock_log:
            SonarrYTDL()
        warning_calls = [str(c) for c in mock_log.warning.call_args_list]
        assert not any('scan_interval' in w for w in warning_calls)


# ---------------------------------------------------------------------------
# TestParseNaming
# ---------------------------------------------------------------------------

class TestParseNaming:

    def test_fallback_defaults_when_keys_missing(self):
        client, _ = make_client()
        client._parse_naming({})
        assert client.season_format == 'Season {season:02d}'
        assert client.number_style == 'S{season:02d}E{episode:02d}'

    def test_fallback_when_only_season_format_present(self):
        client, _ = make_client()
        client._parse_naming({'seasonFolderFormat': 'Season {season:2}'})
        assert client.season_format == 'Season {season:02d}'


# ---------------------------------------------------------------------------
# TestQualityFormat
# ---------------------------------------------------------------------------

class TestQualityFormat:

    def _get_fmt(self, resolution):
        client, mock_sonarr = make_client()
        mock_sonarr.get_quality_profile.return_value = {
            'items': [{'allowed': True, 'quality': {'resolution': resolution}}]
        }
        return client._quality_format(5)

    def test_480p_maps_to_640_width(self):
        assert 'width<=640' in self._get_fmt(480)

    def test_720p_maps_to_1280_width(self):
        assert 'width<=1280' in self._get_fmt(720)

    def test_1080p_maps_to_1920_width(self):
        assert 'width<=1920' in self._get_fmt(1080)

    def test_4k_maps_to_3840_width(self):
        assert 'width<=3840' in self._get_fmt(2160)

    def test_unknown_resolution_defaults_to_1920(self):
        assert 'width<=1920' in self._get_fmt(360)

    def test_disallowed_items_ignored(self):
        client, mock_sonarr = make_client()
        mock_sonarr.get_quality_profile.return_value = {
            'items': [
                {'allowed': False, 'quality': {'resolution': 2160}},
                {'allowed': True, 'quality': {'resolution': 720}},
            ]
        }
        fmt = client._quality_format(5)
        assert 'width<=1280' in fmt


# ---------------------------------------------------------------------------
# TestLibraryFileExists
# ---------------------------------------------------------------------------

class TestLibraryFileExists:

    def _ser(self):
        return {'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}

    def _eps(self):
        return {'seasonNumber': 1, 'episodeNumber': 1}

    def test_returns_false_when_season_dir_missing(self):
        client, _ = make_client()
        assert client._library_file_exists(self._ser(), self._eps()) is False

    def test_returns_true_when_matching_file_exists(self, tmp_path):
        client, _ = make_client()
        client.localpath = str(tmp_path)
        client.path = ''
        season_dir = tmp_path / 'Ms Rachel' / client.season_format.format(season=1)
        season_dir.mkdir(parents=True)
        number = client.number_style.format(season=1, episode=1)
        (season_dir / f'Ms Rachel - {number} - Colours WEBDL.mkv').touch()
        assert client._library_file_exists(self._ser(), self._eps()) is True

    def test_returns_false_when_no_matching_file(self, tmp_path):
        client, _ = make_client()
        client.localpath = str(tmp_path)
        client.path = ''
        season_dir = tmp_path / 'Ms Rachel' / client.season_format.format(season=1)
        season_dir.mkdir(parents=True)
        number = client.number_style.format(season=1, episode=2)  # different episode
        (season_dir / f'Ms Rachel - {number} - Other WEBDL.mkv').touch()
        assert client._library_file_exists(self._ser(), self._eps()) is False


# ---------------------------------------------------------------------------
# TestGetMissingEpisodesAdditional
# ---------------------------------------------------------------------------

class TestGetMissingEpisodesAdditional:

    def test_episode_without_air_date_is_included(self):
        """Episode with no airDateUtc defaults to now and should be included."""
        cfg = {**CFG, 'series': [{'title': 'Ms Rachel', 'url': 'https://youtube.com'}]}
        mock_sonarr = make_sonarr_client(
            series=[{'id': 1, 'title': 'Ms Rachel', 'path': '/tv', 'monitored': True, 'qualityProfileId': 5}],
            episodes=[{'id': 1, 'seriesId': 1, 'title': 'Ep1', 'monitored': True, 'hasFile': False, 'seasonNumber': 1, 'episodeNumber': 1}]
        )
        with patch('sonarr_youtubedl.load_config', return_value=cfg), \
             patch('sonarr_youtubedl.validate_config'), \
             patch('sonarr_youtubedl.SonarrClient', return_value=mock_sonarr), \
         patch.object(mock_sonarr, 'get_health', return_value=[]), \
             patch('sonarr_youtubedl.Notifier'):
            client = SonarrYTDL()
        client.sonarr = mock_sonarr
        series = client.filterseries()
        with patch('sonarr_youtubedl.datetime') as mock_dt:
            mock_dt.now.return_value = NOW
            mock_dt.strptime = datetime.datetime.strptime
            needed = client.get_missing_episodes(series)
        assert len(needed) == 1


# ---------------------------------------------------------------------------
# TestConfigureInit (error handling and config paths)
# ---------------------------------------------------------------------------

class TestConfigureInit:

    def test_configuration_error_exits(self):
        cfg = {**CFG, 'sonarr': {}}  # missing required keys
        with patch('sonarr_youtubedl.load_config', return_value=cfg), \
             patch('sonarr_youtubedl.validate_config'), \
             patch('sonarr_youtubedl.SonarrClient'), \
             patch('sonarr_youtubedl.Notifier'):
            with pytest.raises(SystemExit):
                SonarrYTDL()

    def test_debug_key_missing_defaults_false(self):
        cfg = {**CFG, 'sonarrytdl': {k: v for k, v in CFG['sonarrytdl'].items() if k != 'debug'}}
        client, _ = make_client(cfg=cfg)
        assert client.debug is False

    def test_ssl_true_uses_https(self):
        cfg = {**CFG, 'sonarr': {**CFG['sonarr'], 'ssl': 'true'}}
        client, _ = make_client(cfg=cfg)
        assert client.base_url.startswith('https://')

    def test_ssl_false_uses_http(self):
        client, _ = make_client()
        assert client.base_url.startswith('http://')

    def test_basedir_included_in_base_url(self):
        cfg = {**CFG, 'sonarr': {**CFG['sonarr'], 'basedir': 'sonarr'}}
        client, _ = make_client(cfg=cfg)
        assert '/sonarr' in client.base_url

    def test_subtitles_config_loaded(self):
        cfg = {**CFG, 'ytdl': {
            **CFG['ytdl'],
            'subtitles': {'languages': ['en', 'fr'], 'autogenerated': 'true'}
        }}
        client, _ = make_client(cfg=cfg)
        assert client.ytdl_subtitles is not None
        assert 'en' in client.ytdl_subtitles['languages']

    def test_extra_args_bool_parsed(self):
        cfg = {**CFG, 'ytdl': {**CFG['ytdl'], 'extra_args': {'noplaylist': 'true'}}}
        client, _ = make_client(cfg=cfg)
        assert client.ytdl_extra_args['noplaylist'] is True

    def test_extra_args_int_parsed(self):
        cfg = {**CFG, 'ytdl': {**CFG['ytdl'], 'extra_args': {'concurrent_fragments': '4'}}}
        client, _ = make_client(cfg=cfg)
        assert client.ytdl_extra_args['concurrent_fragments'] == 4

    def test_extra_args_string_fallback(self):
        cfg = {**CFG, 'ytdl': {**CFG['ytdl'], 'extra_args': {'format': 'bestvideo'}}}
        client, _ = make_client(cfg=cfg)
        assert client.ytdl_extra_args['format'] == 'bestvideo'


# ---------------------------------------------------------------------------
# TestConfigureStaging
# ---------------------------------------------------------------------------

class TestConfigureStaging:

    def test_staging_enabled_when_path_set_and_available(self):
        cfg = {**CFG, 'sonarr': {**CFG['sonarr'], 'staging_path': '/sonarr_staging'}}
        mock_sonarr = make_sonarr_client()
        with patch('sonarr_youtubedl.load_config', return_value=cfg), \
             patch('sonarr_youtubedl.validate_config'), \
             patch('sonarr_youtubedl.SonarrClient', return_value=mock_sonarr), \
         patch.object(mock_sonarr, 'get_health', return_value=[]), \
             patch('sonarr_youtubedl.Notifier', return_value=MagicMock()), \
             patch.object(_staging_module, 'is_available', return_value=True), \
             patch.object(_staging_module, 'ensure') as mock_ensure, \
             patch.object(_staging_module, 'clean'), \
             patch.object(_staging_module, 'find_file', return_value=None), \
             patch.object(_staging_module, 'staging_path', return_value='/staging/test.%(ext)s'), \
             patch.object(_staging_module, 'notify_sonarr', return_value=True):
            client = SonarrYTDL()
        assert client.use_staging is True
        mock_ensure.assert_called_once()

    def test_staging_disabled_when_path_set_but_unavailable(self):
        cfg = {**CFG, 'sonarr': {**CFG['sonarr'], 'staging_path': '/sonarr_staging'}}
        mock_sonarr = make_sonarr_client()
        with patch('sonarr_youtubedl.load_config', return_value=cfg), \
             patch('sonarr_youtubedl.validate_config'), \
             patch('sonarr_youtubedl.SonarrClient', return_value=mock_sonarr), \
         patch.object(mock_sonarr, 'get_health', return_value=[]), \
             patch('sonarr_youtubedl.Notifier', return_value=MagicMock()), \
             patch.object(_staging_module, 'is_available', return_value=False), \
             patch.object(_staging_module, 'ensure'), \
             patch.object(_staging_module, 'clean'), \
             patch.object(_staging_module, 'find_file', return_value=None), \
             patch.object(_staging_module, 'staging_path', return_value='/staging/test.%(ext)s'), \
             patch.object(_staging_module, 'notify_sonarr', return_value=True):
            client = SonarrYTDL()
        assert client.use_staging is False


# ---------------------------------------------------------------------------
# TestParseNamingAdditional
# ---------------------------------------------------------------------------

class TestParseNamingAdditional:

    def test_uses_standard_episode_format_when_no_number_style(self):
        client, _ = make_client()
        client._parse_naming({
            'seasonFolderFormat': 'Season {season:2}',
            'standardEpisodeFormat': 'Show S{season:2}E{episode:2} Title',
        })
        assert client.number_style is not None
        assert 'season' in client.number_style

    def test_extract_number_style_returns_default_on_no_match(self):
        client, _ = make_client()
        result = client._extract_number_style('no match here')
        assert result == 'S{season:00}E{episode:00}'

    def test_extract_number_style_extracts_from_full_format(self):
        client, _ = make_client()
        result = client._extract_number_style('Show Name - S{season:2}E{episode:2} - Episode Title')
        assert 'season' in result
        assert 'episode' in result


# ---------------------------------------------------------------------------
# TestSeriesPath
# ---------------------------------------------------------------------------

class TestSeriesPath:

    def test_uses_path_replace_when_path_set(self):
        client, _ = make_client()
        client.path = '/tv'
        client.localpath = '/sonarr_root'
        ser = {'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}
        result = client._series_path(ser)
        assert result == '/sonarr_root/Ms Rachel'

    def test_uses_join_when_path_empty(self):
        client, _ = make_client()
        client.path = ''
        client.localpath = '/sonarr_root'
        ser = {'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}
        result = client._series_path(ser)
        assert result == '/sonarr_root/Ms Rachel'


# ---------------------------------------------------------------------------
# TestDownloadEpisodeStaging
# ---------------------------------------------------------------------------

class TestDownloadEpisodeStaging:

    def _make_staging_client(self):
        cfg = {**CFG, 'sonarr': {**CFG['sonarr'], 'staging_path': '/sonarr_staging'}}
        mock_sonarr = make_sonarr_client()
        with patch('sonarr_youtubedl.load_config', return_value=cfg), \
             patch('sonarr_youtubedl.validate_config'), \
             patch('sonarr_youtubedl.SonarrClient', return_value=mock_sonarr), \
         patch.object(mock_sonarr, 'get_health', return_value=[]), \
             patch('sonarr_youtubedl.Notifier', return_value=MagicMock()), \
             patch.object(_staging_module, 'is_available', return_value=True), \
             patch.object(_staging_module, 'ensure'), \
             patch.object(_staging_module, 'clean'), \
             patch.object(_staging_module, 'find_file', return_value=None), \
             patch.object(_staging_module, 'staging_path', return_value='/staging/test.%(ext)s'), \
             patch.object(_staging_module, 'notify_sonarr', return_value=True):
            client = SonarrYTDL()
        client.sonarr = mock_sonarr
        client.quality_map = {5: 'bestvideo+bestaudio/best'}
        return client, mock_sonarr

    def _ser(self):
        return {
            'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel',
            'qualityProfileId': 5, 'url': 'https://youtube.com',
            'playlistreverse': True, 'cookies_file': None, 'subtitles': None,
        }

    def _eps(self):
        return {'id': 1, 'seriesId': 1, 'title': 'Colours', 'seasonNumber': 1, 'episodeNumber': 1}

    def test_resumes_existing_staged_file(self):
        client, _ = self._make_staging_client()
        with patch.object(_staging_module, 'find_file', return_value='/staging/Ms Rachel - S1E1.mkv'), \
             patch.object(_staging_module, 'notify_sonarr', return_value=True) as mock_notify:
            result = client._download_episode(self._ser(), self._eps())
        assert result is True
        mock_notify.assert_called_once()

    def test_fallback_called_when_notify_sonarr_fails_on_resume(self):
        client, _ = self._make_staging_client()
        with patch.object(_staging_module, 'find_file', return_value='/staging/Ms Rachel - S1E1.mkv'), \
             patch.object(_staging_module, 'notify_sonarr', return_value=False), \
             patch.object(_staging_module, '_fallback') as mock_fallback:
            client._download_episode(self._ser(), self._eps())
        mock_fallback.assert_called_once()

    def test_staging_path_used_for_outtmpl(self):
        client, _ = self._make_staging_client()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch.object(_staging_module, 'find_file', side_effect=[None, '/staging/Ms Rachel - S1E1.mkv']), \
             patch.object(_staging_module, 'staging_path', return_value='/staging/Ms Rachel - S1E1.%(ext)s') as mock_sp, \
             patch.object(_staging_module, 'notify_sonarr', return_value=True), \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.return_value = True
            client._download_episode(self._ser(), self._eps())
        mock_sp.assert_called_once()

    def test_error_logged_when_staged_file_missing_after_download(self):
        client, _ = self._make_staging_client()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch.object(_staging_module, 'find_file', return_value=None), \
             patch.object(_staging_module, 'staging_path', return_value='/staging/test.%(ext)s'), \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.return_value = True
            result = client._download_episode(self._ser(), self._eps())
        assert result is False

    def test_fallback_called_when_notify_sonarr_fails_after_download(self):
        client, _ = self._make_staging_client()
        with patch('sonarr_youtubedl.downloader') as mock_dl, \
             patch.object(client, '_library_file_exists', return_value=False), \
             patch.object(_staging_module, 'find_file', return_value='/staging/Ms Rachel - S1E1.mkv'), \
             patch.object(_staging_module, 'staging_path', return_value='/staging/test.%(ext)s'), \
             patch.object(_staging_module, 'notify_sonarr', return_value=False), \
             patch.object(_staging_module, '_fallback') as mock_fallback, \
             patch('sonarr_youtubedl.time.sleep'):
            mock_dl.search.return_value = 'https://youtube.com/watch?v=123'
            mock_dl.download.return_value = True
            client._download_episode(self._ser(), self._eps())
        mock_fallback.assert_called_once()


# ---------------------------------------------------------------------------
# TestDownloadWithStaging
# ---------------------------------------------------------------------------

class TestDownloadWithStaging:

    def test_staging_clean_called_at_start(self):
        cfg = {**CFG, 'sonarr': {**CFG['sonarr'], 'staging_path': '/sonarr_staging'}}
        mock_sonarr = make_sonarr_client()
        with patch('sonarr_youtubedl.load_config', return_value=cfg), \
             patch('sonarr_youtubedl.validate_config'), \
             patch('sonarr_youtubedl.SonarrClient', return_value=mock_sonarr), \
         patch.object(mock_sonarr, 'get_health', return_value=[]), \
             patch('sonarr_youtubedl.Notifier', return_value=MagicMock()), \
             patch.object(_staging_module, 'is_available', return_value=True), \
             patch.object(_staging_module, 'ensure'), \
             patch.object(_staging_module, 'clean') as mock_clean, \
             patch.object(_staging_module, 'find_file', return_value=None), \
             patch.object(_staging_module, 'staging_path', return_value='/staging/test.%(ext)s'), \
             patch.object(_staging_module, 'notify_sonarr', return_value=True):
            client = SonarrYTDL()
            client.sonarr = mock_sonarr
            ser = {'id': 1, 'title': 'Ms Rachel', 'path': '/tv', 'qualityProfileId': 5,
                   'url': 'https://youtube.com', 'playlistreverse': True,
                   'cookies_file': None, 'subtitles': None, 'min_check_interval': 0}
            client.download([ser], [])
        mock_clean.assert_called_once()


# ---------------------------------------------------------------------------
# TestFilterseriesAdditional
# ---------------------------------------------------------------------------

class TestFilterseriesAdditional:

    def test_format_set_from_config(self):
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]',
        }]}
        client, _ = make_client(cfg=cfg)
        result = client.filterseries()
        assert result[0]['format'] == 'bestvideo[ext=mp4]+bestaudio[ext=m4a]'

    def test_per_series_subtitles_override_global(self):
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
            'subtitles': {'languages': ['fr'], 'autogenerated': 'true'},
        }]}
        client, _ = make_client(cfg=cfg)
        result = client.filterseries()
        assert result[0]['subtitles']['languages'] == ['fr']

    def test_site_regex_set_from_config(self):
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
            'regex': {'site': {'match': r'^Ms Rachel - ', 'replace': ''}},
        }]}
        client, _ = make_client(cfg=cfg)
        result = client.filterseries()
        assert result[0]['site_regex'] == {'match': r'^Ms Rachel - ', 'replace': ''}

    def test_per_series_extra_args_parsed(self):
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
            'extra_args': {'playlistend': '10', 'sponsorblock_remove': 'sponsor'},
        }]}
        client, _ = make_client(cfg=cfg)
        result = client.filterseries()
        assert result[0]['extra_args']['playlistend'] == 10
        assert result[0]['extra_args']['sponsorblock_remove'] == 'sponsor'

    def test_per_series_extra_args_bool_parsed(self):
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
            'extra_args': {'noplaylist': 'true'},
        }]}
        client, _ = make_client(cfg=cfg)
        result = client.filterseries()
        assert result[0]['extra_args']['noplaylist'] is True

    def test_per_series_extra_args_not_set_when_absent(self):
        cfg = {**CFG, 'series': [{
            'title': 'Ms Rachel',
            'url': 'https://youtube.com/channel/msrachel',
        }]}
        client, _ = make_client(cfg=cfg)
        result = client.filterseries()
        assert 'extra_args' not in result[0]



# ---------------------------------------------------------------------------
# TestDownloadEpisodeFiltering
# ---------------------------------------------------------------------------

class TestDownloadEpisodeFiltering:

    def test_episode_with_different_series_id_skipped(self):
        client, _ = make_client()
        client.quality_map = {5: 'bestvideo+bestaudio/best'}
        ser = {
            'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel',
            'qualityProfileId': 5, 'url': 'https://youtube.com',
            'playlistreverse': True, 'cookies_file': None,
            'subtitles': None, 'min_check_interval': 0,
        }
        # Episode belongs to series id 99, not 1
        eps = [{'id': 1, 'seriesId': 99, 'title': 'Ep1', 'seasonNumber': 1, 'episodeNumber': 1}]
        with patch.object(client, '_download_episode') as mock_dl_ep:
            client.download([ser], eps)
        mock_dl_ep.assert_not_called()