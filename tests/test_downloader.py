import os
import sys
import importlib
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault('CONFIGPATH', '/config/config.yml')
sys.path.insert(0, os.path.dirname(__file__))

# Stub yt_dlp if not installed (CI environment)
if 'yt_dlp' not in sys.modules:
    sys.modules['yt_dlp'] = MagicMock()

# Force import of the real downloader module regardless of test execution order.
# test_sonarr_youtubedl.py stubs sys.modules['downloader'] at collection time,
# which would cause all yt_dlp patches to fail with AttributeError.
import downloader
importlib.reload(downloader)

PLAYLIST_URL = 'https://youtube.com/channel/msrachel'
VIDEO_URL = 'https://youtube.com/watch?v=abc123'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ydl_context(result):
    """Return a mock yt_dlp.YoutubeDL context manager yielding result."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.extract_info.return_value = result
    return mock


def make_entries(*titles):
    """Build a list of playlist entry dicts."""
    return [
        {'title': t, 'webpage_url': f'https://youtube.com/watch?v={i}'}
        for i, t in enumerate(titles)
    ]


# ---------------------------------------------------------------------------
# TestPotArgs
# ---------------------------------------------------------------------------

class TestPotArgs:

    def test_extractor_args_present(self):
        pot = downloader._pot_args()
        assert 'extractor_args' in pot

    def test_bgutil_server_home_set(self):
        pot = downloader._pot_args()
        server_home = pot['extractor_args']['youtubepot-bgutilscript']['server_home']
        assert downloader.BGUTIL_SERVER in server_home

    def test_js_runtimes_present(self):
        pot = downloader._pot_args()
        assert 'js_runtimes' in pot
        assert 'node' in pot['js_runtimes']

    def test_node_path_set(self):
        pot = downloader._pot_args()
        assert pot['js_runtimes']['node']['path'] == downloader.NODE_PATH


# ---------------------------------------------------------------------------
# TestSearch
# ---------------------------------------------------------------------------

class TestSearch:

    # --- Error handling ---

    def test_yt_dlp_exception_returns_none(self):
        with patch('downloader.yt_dlp.YoutubeDL', side_effect=Exception('network error')):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) is None

    def test_none_result_returns_none(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context(None)):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) is None

    def test_empty_dict_result_returns_none(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({})):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) is None

    # --- Single video (no entries) ---

    def test_single_video_returns_webpage_url(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'webpage_url': VIDEO_URL})):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) == VIDEO_URL

    def test_single_video_falls_back_to_url_key(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'url': VIDEO_URL})):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) == VIDEO_URL

    def test_single_video_returns_none_when_url_equals_playlist(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'webpage_url': PLAYLIST_URL})):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) is None

    def test_single_video_returns_none_when_no_url(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'title': 'something'})):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) is None

    # --- Entries: filtering ---

    def test_all_none_entries_returns_none(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': [None, None]})):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) is None

    def test_empty_entries_returns_none(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': []})):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) is None

    def test_none_entries_filtered_out(self):
        entries = [None, {'title': 'Ms Rachel - Colours', 'webpage_url': VIDEO_URL}]
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})):
            assert downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True) == VIDEO_URL

    # --- Entries: regex matching ---

    def test_regex_match_returns_correct_entry(self):
        entries = make_entries('Ms Rachel - Colours and Shapes', 'Ms Rachel - ABC Song')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})):
            result = downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours and Shapes', True)
        assert result == entries[0]['webpage_url']

    def test_regex_match_case_insensitive(self):
        entries = make_entries('MS RACHEL - COLOURS AND SHAPES', 'Ms Rachel - ABC Song')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})):
            result = downloader.search(PLAYLIST_URL, 'Ms Rachel', 'colours and shapes', True)
        assert result == entries[0]['webpage_url']

    def test_no_regex_match_falls_back_to_fuzzy(self):
        entries = make_entries('Ms Rachel - Colours and Shapes', 'Ms Rachel - ABC Song')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})):
            # Title won't regex match exactly but fuzzy should pick closest
            result = downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours and Shapes for Toddlers', True)
        assert result is not None

    def test_result_url_falls_back_to_url_key(self):
        entries = [{'title': 'Ms Rachel - Colours', 'url': VIDEO_URL}]
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})):
            result = downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True)
        assert result == VIDEO_URL

    def test_result_none_when_matched_url_equals_playlist(self):
        entries = [{'title': 'Ms Rachel - Colours', 'webpage_url': PLAYLIST_URL}]
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})):
            result = downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True)
        assert result is None

    # --- Options wiring ---

    def test_cookies_added_to_opts(self):
        entries = make_entries('Ms Rachel - Colours')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})) as MockYDL:
            downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True, cookies='/config/cookies.txt')
        assert MockYDL.call_args[0][0].get('cookiefile') == '/config/cookies.txt'

    def test_no_cookies_when_none(self):
        entries = make_entries('Ms Rachel - Colours')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})) as MockYDL:
            downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True)
        assert 'cookiefile' not in MockYDL.call_args[0][0]

    def test_extra_args_merged_into_opts(self):
        entries = make_entries('Ms Rachel - Colours')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})) as MockYDL:
            downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True, extra_args={'socket_timeout': 60})
        assert MockYDL.call_args[0][0].get('socket_timeout') == 60

    def test_debug_mode_sets_quiet_false(self):
        entries = make_entries('Ms Rachel - Colours')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})) as MockYDL:
            downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True, debug=True)
        assert MockYDL.call_args[0][0].get('quiet') is False

    def test_debug_mode_adds_logger(self):
        entries = make_entries('Ms Rachel - Colours')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})) as MockYDL:
            downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True, debug=True)
        assert 'logger' in MockYDL.call_args[0][0]

    def test_pot_args_included_in_opts(self):
        entries = make_entries('Ms Rachel - Colours')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})) as MockYDL:
            downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True)
        opts = MockYDL.call_args[0][0]
        assert 'extractor_args' in opts
        assert 'js_runtimes' in opts

    def test_extract_flat_enabled(self):
        entries = make_entries('Ms Rachel - Colours')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})) as MockYDL:
            downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True)
        assert MockYDL.call_args[0][0].get('extract_flat') is True


# ---------------------------------------------------------------------------
# TestDownload
# ---------------------------------------------------------------------------

    def test_best_match_exception_returns_none(self):
        entries = make_entries('Ms Rachel - Colours')
        with patch('downloader.yt_dlp.YoutubeDL', return_value=make_ydl_context({'entries': entries})),              patch('downloader.find_best_match_index', side_effect=Exception('match error')):
            result = downloader.search(PLAYLIST_URL, 'Ms Rachel', 'Colours', True)
        assert result is None


class TestDownload:

    # --- Return values ---

    def test_returns_true_on_success(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()):
            assert downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo') is True

    def test_returns_false_on_exception(self):
        with patch('downloader.yt_dlp.YoutubeDL', side_effect=Exception('failed')):
            assert downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo') is False

    def test_logs_error_on_exception(self):
        with patch('downloader.yt_dlp.YoutubeDL', side_effect=Exception('failed')), \
             patch.object(downloader.logger, 'error') as mock_error:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo')
        mock_error.assert_called_once()

    # --- Options wiring ---

    def test_format_set_in_opts(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo[width<=1920]')
        assert MockYDL.call_args[0][0].get('format') == 'bestvideo[width<=1920]'

    def test_outtmpl_set_in_opts(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/sonarr_root/Ms Rachel/S01E01.%(ext)s', 'bestvideo')
        assert MockYDL.call_args[0][0].get('outtmpl') == '/sonarr_root/Ms Rachel/S01E01.%(ext)s'

    def test_noplaylist_set_in_opts(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo')
        assert MockYDL.call_args[0][0].get('noplaylist') is True

    def test_cookies_added_to_opts(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo', cookies='/config/cookies.txt')
        assert MockYDL.call_args[0][0].get('cookiefile') == '/config/cookies.txt'

    def test_no_cookies_when_none(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo')
        assert 'cookiefile' not in MockYDL.call_args[0][0]

    def test_extra_args_merged_into_opts(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo', extra_args={'concurrent_fragments': 4})
        assert MockYDL.call_args[0][0].get('concurrent_fragments') == 4

    def test_subtitles_opts_included(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo',
                                subtitles={'languages': ['en'], 'autogenerated': True})
        opts = MockYDL.call_args[0][0]
        assert opts.get('writesubtitles') is True
        assert opts.get('subtitleslangs') == ['en']
        assert opts.get('writeautomaticsub') is True

    def test_subtitles_postprocessors_included(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo',
                                subtitles={'languages': ['en'], 'autogenerated': False})
        opts = MockYDL.call_args[0][0]
        keys = [p['key'] for p in opts.get('postprocessors', [])]
        assert 'FFmpegSubtitlesConvertor' in keys
        assert 'FFmpegEmbedSubtitle' in keys

    def test_no_subtitles_opts_when_none(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo')
        opts = MockYDL.call_args[0][0]
        assert 'writesubtitles' not in opts

    def test_debug_mode_sets_quiet_false(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo', debug=True)
        assert MockYDL.call_args[0][0].get('quiet') is False

    def test_debug_mode_adds_logger(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo', debug=True)
        assert 'logger' in MockYDL.call_args[0][0]

    def test_pot_args_included_in_opts(self):
        with patch('downloader.yt_dlp.YoutubeDL', return_value=MagicMock()) as MockYDL:
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo')
        opts = MockYDL.call_args[0][0]
        assert 'extractor_args' in opts
        assert 'js_runtimes' in opts

    def test_download_called_with_correct_url(self):
        mock_ydl = MagicMock()
        with patch('downloader.yt_dlp.YoutubeDL', return_value=mock_ydl):
            downloader.download(VIDEO_URL, '/out.%(ext)s', 'bestvideo')
        mock_ydl.download.assert_called_once_with([VIDEO_URL])