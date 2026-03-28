import os
import sys
import importlib
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault('CONFIGPATH', '/config/config.yml')
sys.path.insert(0, os.path.dirname(__file__))

# Force import of the real sonarr_client module regardless of test execution order.
import sonarr_client
importlib.reload(sonarr_client)
from sonarr_client import SonarrClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_client():
    return SonarrClient('http://sonarr:8989', 'api/v3', 'testkey123')


def mock_get(return_value=None):
    mock = MagicMock()
    mock.return_value = MagicMock(json=MagicMock(return_value=return_value or []))
    return mock


def mock_post(return_value=None):
    mock = MagicMock()
    mock.return_value = MagicMock(json=MagicMock(return_value=return_value or {'id': 1}))
    return mock


# ---------------------------------------------------------------------------
# TestSonarrClientInit
# ---------------------------------------------------------------------------

class TestSonarrClientInit:

    def test_base_url_stored(self):
        client = SonarrClient('http://sonarr:8989', 'api/v3', 'mykey')
        assert client.base_url == 'http://sonarr:8989'

    def test_api_version_stored(self):
        client = SonarrClient('http://sonarr:8989', 'api/v3', 'mykey')
        assert client.api_version == 'api/v3'

    def test_api_key_stored(self):
        client = SonarrClient('http://sonarr:8989', 'api/v3', 'mykey')
        assert client.api_key == 'mykey'


# ---------------------------------------------------------------------------
# TestGet
# ---------------------------------------------------------------------------

class TestGet:

    def test_url_contains_base_url_and_version_and_endpoint(self):
        client = make_client()
        with patch('sonarr_client.requests.get', mock_get([])):
            client.get_series()
        # Verify by checking get_series works - URL tested via call_args below
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=[]))
            client.get_series()
            url = mock.call_args[0][0]
        assert 'http://sonarr:8989/api/v3/series' in url

    def test_apikey_included_in_url(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=[]))
            client.get_series()
            url = mock.call_args[0][0]
        assert 'apikey=testkey123' in url

    def test_extra_params_included_in_url(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=[]))
            client.get_episodes(5)
            url = mock.call_args[0][0]
        assert 'seriesId=5' in url

    def test_timeout_set(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=[]))
            client.get_series()
        assert mock.call_args[1]['timeout'] == 30

    def test_returns_parsed_json(self):
        client = make_client()
        expected = [{'id': 1, 'title': 'Ms Rachel'}]
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=expected))
            result = client.get_series()
        assert result == expected


# ---------------------------------------------------------------------------
# TestPost
# ---------------------------------------------------------------------------

class TestPost:

    def test_url_contains_base_url_and_version_and_endpoint(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.refresh(1)
            url = mock.call_args[0][0]
        assert 'http://sonarr:8989/api/v3/command' in url

    def test_apikey_in_params(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.refresh(1)
            params = mock.call_args[1]['params']
        assert ('apikey', 'testkey123') in params

    def test_content_type_header_set(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.refresh(1)
            headers = mock.call_args[1]['headers']
        assert headers.get('Content-Type') == 'application/json'

    def test_timeout_set(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.refresh(1)
        assert mock.call_args[1]['timeout'] == 30

    def test_returns_parsed_json(self):
        client = make_client()
        expected = {'id': 42, 'status': 'queued'}
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=expected))
            result = client.refresh(1)
        assert result == expected


# ---------------------------------------------------------------------------
# TestGetSeries
# ---------------------------------------------------------------------------

class TestGetSeries:

    def test_calls_series_endpoint(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=[]))
            client.get_series()
            url = mock.call_args[0][0]
        assert '/series' in url

    def test_returns_series_list(self):
        client = make_client()
        expected = [{'id': 1, 'title': 'Ms Rachel'}]
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=expected))
            assert client.get_series() == expected


# ---------------------------------------------------------------------------
# TestGetEpisodes
# ---------------------------------------------------------------------------

class TestGetEpisodes:

    def test_calls_episode_endpoint(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=[]))
            client.get_episodes(5)
            url = mock.call_args[0][0]
        assert '/episode' in url

    def test_series_id_in_params(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=[]))
            client.get_episodes(5)
            url = mock.call_args[0][0]
        assert 'seriesId=5' in url


# ---------------------------------------------------------------------------
# TestGetQualityProfile
# ---------------------------------------------------------------------------

class TestGetQualityProfile:

    def test_calls_qualityprofile_endpoint_with_id(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={}))
            client.get_quality_profile(3)
            url = mock.call_args[0][0]
        assert 'qualityprofile/3' in url


# ---------------------------------------------------------------------------
# TestGetNamingConfig
# ---------------------------------------------------------------------------

class TestGetNamingConfig:

    def test_calls_naming_config_endpoint(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={}))
            client.get_naming_config()
            url = mock.call_args[0][0]
        assert 'config/naming' in url


# ---------------------------------------------------------------------------
# TestRefresh
# ---------------------------------------------------------------------------

class TestRefresh:

    def test_sends_refresh_series_command(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.refresh(42)
            body = mock.call_args[1]['json']
        assert body['name'] == 'RefreshSeries'

    def test_series_id_cast_to_string(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.refresh(42)
            body = mock.call_args[1]['json']
        assert body['seriesId'] == '42'


# ---------------------------------------------------------------------------
# TestRescan
# ---------------------------------------------------------------------------

class TestRescan:

    def test_sends_rescan_series_command(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.rescan(42)
            body = mock.call_args[1]['json']
        assert body['name'] == 'RescanSeries'

    def test_series_id_cast_to_string(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.rescan(42)
            body = mock.call_args[1]['json']
        assert body['seriesId'] == '42'


# ---------------------------------------------------------------------------
# TestDownloadedEpisodesScan
# ---------------------------------------------------------------------------

class TestDownloadedEpisodesScan:

    def test_sends_downloaded_episodes_scan_command(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.downloaded_episodes_scan('/staging/ep.mkv')
            body = mock.call_args[1]['json']
        assert body['name'] == 'DownloadedEpisodesScan'

    def test_path_included_in_body(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.downloaded_episodes_scan('/staging/Ms Rachel - S01E01.mkv')
            body = mock.call_args[1]['json']
        assert body['path'] == '/staging/Ms Rachel - S01E01.mkv'

    def test_import_mode_is_move(self):
        client = make_client()
        with patch('sonarr_client.requests.post') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value={'id': 1}))
            client.downloaded_episodes_scan('/staging/ep.mkv')
            body = mock.call_args[1]['json']
        assert body['importMode'] == 'Move'

# ---------------------------------------------------------------------------
# TestGetHealth
# ---------------------------------------------------------------------------

class TestGetHealth:

    def test_calls_health_endpoint(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=[]))
            client.get_health()
            url = mock.call_args[0][0]
        assert 'health' in url

    def test_returns_empty_list_when_healthy(self):
        client = make_client()
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=[]))
            assert client.get_health() == []

    def test_returns_issues_when_present(self):
        client = make_client()
        issues = [{'type': 'warning', 'message': 'Indexer unavailable', 'source': 'IndexerStatusCheck'}]
        with patch('sonarr_client.requests.get') as mock:
            mock.return_value = MagicMock(json=MagicMock(return_value=issues))
            assert client.get_health() == issues