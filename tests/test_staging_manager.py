import os
import sys
import time
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

import staging_manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_staging_file(directory, filename='Ms Rachel - S01E01.mkv', age_minutes=0):
    """Create a file in directory, optionally backdating its mtime."""
    path = os.path.join(directory, filename)
    open(path, 'w').close()
    if age_minutes:
        old_time = time.time() - (age_minutes * 60)
        os.utime(path, (old_time, old_time))
    return path


def make_client(series=None):
    mock = MagicMock()
    mock.get_series.return_value = series if series is not None else [
        {'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}
    ]
    mock.downloaded_episodes_scan.return_value = {'id': 123}
    return mock


# ---------------------------------------------------------------------------
# TestIsAvailable
# ---------------------------------------------------------------------------

class TestIsAvailable:

    def test_true_for_existing_writable_dir(self, tmp_path):
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)):
            assert staging_manager.is_available() is True

    def test_false_for_missing_dir(self):
        with patch.object(staging_manager, 'STAGING_DIR', '/nonexistent/staging'):
            assert staging_manager.is_available() is False

    def test_false_for_unwritable_dir(self, tmp_path):
        os.chmod(str(tmp_path), 0o444)
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)):
            result = staging_manager.is_available()
        os.chmod(str(tmp_path), 0o755)  # restore for cleanup
        if os.getuid() == 0:
            pytest.skip("Running as root — permission checks do not apply")
        assert result is False


# ---------------------------------------------------------------------------
# TestEnsure
# ---------------------------------------------------------------------------

class TestEnsure:

    def test_creates_directory_when_missing(self, tmp_path):
        staging = str(tmp_path / 'staging')
        with patch.object(staging_manager, 'STAGING_DIR', staging):
            staging_manager.ensure()
        assert os.path.isdir(staging)

    def test_does_not_raise_if_already_exists(self, tmp_path):
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)):
            staging_manager.ensure()
            staging_manager.ensure()  # second call should not raise


# ---------------------------------------------------------------------------
# TestFindFile
# ---------------------------------------------------------------------------

class TestFindFile:

    def test_returns_path_when_file_exists(self, tmp_path):
        make_staging_file(tmp_path, 'Ms Rachel - S01E01.mkv')
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)):
            result = staging_manager.find_file('Ms Rachel', 'S01E01')
        assert result == str(tmp_path / 'Ms Rachel - S01E01.mkv')

    def test_returns_none_when_not_found(self, tmp_path):
        make_staging_file(tmp_path, 'Ms Rachel - S01E01.mkv')
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)):
            result = staging_manager.find_file('Ms Rachel', 'S01E02')
        assert result is None

    def test_returns_none_when_staging_empty(self, tmp_path):
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)):
            result = staging_manager.find_file('Ms Rachel', 'S01E01')
        assert result is None

    def test_matches_by_prefix_not_substring(self, tmp_path):
        make_staging_file(tmp_path, 'Ms Rachel - S01E01.mkv')
        make_staging_file(tmp_path, 'Ms Rachel Show - S01E01.mkv')
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)):
            result = staging_manager.find_file('Ms Rachel', 'S01E01')
        assert os.path.basename(result) == 'Ms Rachel - S01E01.mkv'

    def test_different_extensions_found(self, tmp_path):
        make_staging_file(tmp_path, 'Ms Rachel - S01E01.mp4')
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)):
            result = staging_manager.find_file('Ms Rachel', 'S01E01')
        assert result == str(tmp_path / 'Ms Rachel - S01E01.mp4')


# ---------------------------------------------------------------------------
# TestStagingPath
# ---------------------------------------------------------------------------

class TestStagingPath:

    def test_returns_correct_template(self):
        with patch.object(staging_manager, 'STAGING_DIR', '/staging'):
            result = staging_manager.staging_path('Ms Rachel', 'S01E01')
        assert result == '/staging/Ms Rachel - S01E01.%(ext)s'

    def test_includes_series_and_number(self):
        with patch.object(staging_manager, 'STAGING_DIR', '/staging'):
            result = staging_manager.staging_path('Peppa Pig', 'S02E05')
        assert 'Peppa Pig' in result
        assert 'S02E05' in result


# ---------------------------------------------------------------------------
# TestNotifySonarr
# ---------------------------------------------------------------------------

class TestNotifySonarr:

    def test_returns_true_on_success(self):
        client = make_client()
        result = staging_manager.notify_sonarr(client, '/staging/Ms Rachel - S01E01.mkv', '/sonarr_staging')
        assert result is True

    def test_returns_false_when_id_missing(self):
        client = make_client()
        client.downloaded_episodes_scan.return_value = {}
        result = staging_manager.notify_sonarr(client, '/staging/Ms Rachel - S01E01.mkv', '/sonarr_staging')
        assert result is False

    def test_calls_scan_with_correct_sonarr_path(self):
        client = make_client()
        staging_manager.notify_sonarr(client, '/staging/Ms Rachel - S01E01.mkv', '/sonarr_staging')
        client.downloaded_episodes_scan.assert_called_once_with('/sonarr_staging/Ms Rachel - S01E01.mkv')

    def test_logs_warning_on_rejection(self):
        client = make_client()
        client.downloaded_episodes_scan.return_value = {}
        with patch.object(staging_manager.logger, 'warning') as mock_warning:
            staging_manager.notify_sonarr(client, '/staging/Ms Rachel - S01E01.mkv', '/sonarr_staging')
        mock_warning.assert_called_once()


# ---------------------------------------------------------------------------
# TestClean
# ---------------------------------------------------------------------------

class TestClean:

    def test_does_nothing_when_staging_not_available(self, tmp_path):
        client = make_client()
        with patch.object(staging_manager, 'STAGING_DIR', '/nonexistent'):
            staging_manager.clean(client, 'Season {season:02d}', '', str(tmp_path))
        client.get_series.assert_not_called()

    def test_ignores_fresh_files(self, tmp_path):
        make_staging_file(tmp_path, 'Ms Rachel - S01E01.mkv', age_minutes=5)
        client = make_client()
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)), \
             patch('staging_manager._fallback') as mock_fallback:
            staging_manager.clean(client, 'Season {season:02d}', '', str(tmp_path))
        mock_fallback.assert_not_called()

    def test_calls_fallback_for_stale_files(self, tmp_path):
        make_staging_file(tmp_path, 'Ms Rachel - S01E01.mkv', age_minutes=90)
        client = make_client()
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)), \
             patch('staging_manager._fallback') as mock_fallback:
            staging_manager.clean(client, 'Season {season:02d}', '', str(tmp_path))
        mock_fallback.assert_called_once()

    def test_ignores_directories(self, tmp_path):
        subdir = tmp_path / 'somedir'
        subdir.mkdir()
        client = make_client()
        with patch.object(staging_manager, 'STAGING_DIR', str(tmp_path)), \
             patch('staging_manager._fallback') as mock_fallback:
            staging_manager.clean(client, 'Season {season:02d}', '', str(tmp_path))
        mock_fallback.assert_not_called()


# ---------------------------------------------------------------------------
# TestFallback
# ---------------------------------------------------------------------------

class TestFallback:

    def test_moves_file_to_library(self, tmp_path):
        staging_dir = tmp_path / 'staging'
        staging_dir.mkdir()
        lib_dir = tmp_path / 'library'
        staging_file = make_staging_file(staging_dir, 'Ms Rachel - S01E01.mkv')
        client = make_client(series=[{'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}])
        with patch('staging_manager.time.sleep'):
            staging_manager._fallback(client, staging_file, 'Season {season:02d}', '', str(lib_dir))
        expected = lib_dir / 'Ms Rachel' / 'Season 01' / 'Ms Rachel - S01E01 WEBDL.mkv'
        assert expected.exists()

    def test_triggers_refresh_and_rescan(self, tmp_path):
        staging_dir = tmp_path / 'staging'
        staging_dir.mkdir()
        lib_dir = tmp_path / 'library'
        staging_file = make_staging_file(staging_dir, 'Ms Rachel - S01E01.mkv')
        client = make_client(series=[{'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}])
        with patch('staging_manager.time.sleep'):
            staging_manager._fallback(client, staging_file, 'Season {season:02d}', '', str(lib_dir))
        client.refresh.assert_called_once_with(1)
        client.rescan.assert_called_once_with(1)

    def test_uses_path_mapping_when_provided(self, tmp_path):
        staging_dir = tmp_path / 'staging'
        staging_dir.mkdir()
        lib_dir = tmp_path / 'library'
        staging_file = make_staging_file(staging_dir, 'Ms Rachel - S01E01.mkv')
        client = make_client(series=[{'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}])
        with patch('staging_manager.time.sleep'):
            staging_manager._fallback(client, staging_file, 'Season {season:02d}', '/tv', str(lib_dir))
        expected = lib_dir / 'Ms Rachel' / 'Season 01' / 'Ms Rachel - S01E01 WEBDL.mkv'
        assert expected.exists()

    def test_logs_error_for_unparseable_filename(self, tmp_path):
        staging_file = make_staging_file(tmp_path, 'badname.mkv')
        client = make_client()
        with patch.object(staging_manager.logger, 'error') as mock_error:
            staging_manager._fallback(client, staging_file, 'Season {season:02d}', '', str(tmp_path))
        mock_error.assert_called_once()
        assert 'Cannot parse' in str(mock_error.call_args)

    def test_logs_error_when_series_not_found(self, tmp_path):
        staging_dir = tmp_path / 'staging'
        staging_dir.mkdir()
        staging_file = make_staging_file(staging_dir, 'Ms Rachel - S01E01.mkv')
        client = make_client(series=[])  # empty - series not found
        with patch.object(staging_manager.logger, 'error') as mock_error:
            staging_manager._fallback(client, staging_file, 'Season {season:02d}', '', str(tmp_path))
        mock_error.assert_called_once()
        assert 'not found' in str(mock_error.call_args)

    def test_logs_error_on_move_failure(self, tmp_path):
        staging_dir = tmp_path / 'staging'
        staging_dir.mkdir()
        staging_file = make_staging_file(staging_dir, 'Ms Rachel - S01E01.mkv')
        client = make_client(series=[{'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}])
        with patch('staging_manager.shutil.move', side_effect=OSError('permission denied')), \
             patch.object(staging_manager.logger, 'error') as mock_error:
            staging_manager._fallback(client, staging_file, 'Season {season:02d}', '', str(tmp_path))
        assert any('Fallback move failed' in str(c) for c in mock_error.call_args_list)


    def test_does_not_rescan_when_season_number_unparseable(self, tmp_path):
        staging_dir = tmp_path / 'staging'
        staging_dir.mkdir()
        staging_file = make_staging_file(staging_dir, 'Ms Rachel - SxxE01.mkv')
        client = make_client(series=[{'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}])
        staging_manager._fallback(client, staging_file, 'Season {season:02d}', '', str(tmp_path))
        client.refresh.assert_not_called()
        client.rescan.assert_not_called()

    def test_does_not_rescan_on_move_failure(self, tmp_path):
        staging_dir = tmp_path / 'staging'
        staging_dir.mkdir()
        staging_file = make_staging_file(staging_dir, 'Ms Rachel - S01E01.mkv')
        client = make_client(series=[{'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}])
        with patch('staging_manager.shutil.move', side_effect=OSError('permission denied')):
            staging_manager._fallback(client, staging_file, 'Season {season:02d}', '', str(tmp_path))
        client.refresh.assert_not_called()
        client.rescan.assert_not_called()

    def test_preserves_file_extension(self, tmp_path):
        staging_dir = tmp_path / 'staging'
        staging_dir.mkdir()
        lib_dir = tmp_path / 'library'
        staging_file = make_staging_file(staging_dir, 'Ms Rachel - S01E01.mp4')
        client = make_client(series=[{'id': 1, 'title': 'Ms Rachel', 'path': '/tv/Ms Rachel'}])
        with patch('staging_manager.time.sleep'):
            staging_manager._fallback(client, staging_file, 'Season {season:02d}', '', str(lib_dir))
        expected = lib_dir / 'Ms Rachel' / 'Season 01' / 'Ms Rachel - S01E01 WEBDL.mp4'
        assert expected.exists()