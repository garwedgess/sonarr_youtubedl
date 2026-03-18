import re
import datetime
import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault('CONFIGPATH', '/config/config.yml')
from utils import escapetitle, upperescape, find_best_match_index, offsethandler


# ---------------------------------------------------------------------------
# escapetitle / upperescape
# ---------------------------------------------------------------------------

class TestEscapetitle:

    def _matches(self, episode_title, candidate):
        """Returns True if escapetitle(episode_title) matches candidate."""
        pattern = escapetitle(episode_title)
        return bool(re.search(pattern, candidate, re.IGNORECASE))

    # --- Alias ---

    def test_upperescape_alias_identical(self):
        assert upperescape("Hello World") == escapetitle("Hello World")

    # --- No uppercasing ---

    def test_does_not_uppercase_output(self):
        pattern = escapetitle("kids show")
        assert 'KIDS' not in pattern
        assert 'SHOW' not in pattern

    def test_no_regex_metachar_mangling(self):
        # Verify \d is not mangled to \D (the original bug)
        pattern = escapetitle("episode 5")
        assert '\\D' not in pattern

    # --- Basic matching ---

    def test_exact_match(self):
        assert self._matches("Learn With Ms Rachel", "Learn With Ms Rachel")

    def test_case_insensitive_lower_to_upper(self):
        assert self._matches("learn with ms rachel", "LEARN WITH MS RACHEL")

    def test_case_insensitive_upper_to_lower(self):
        assert self._matches("LEARN WITH MS RACHEL", "learn with ms rachel")

    def test_no_match_completely_different(self):
        assert not self._matches("Learn With Ms Rachel", "Peppa Pig Season 3")

    def test_partial_word_no_spurious_match(self):
        assert not self._matches("The Cat Show", "The Concatenate Show")

    # --- Title prefix variations ---

    def test_show_colon_episode(self):
        assert self._matches("Colours and Shapes", "Ms Rachel: Colours and Shapes")

    def test_show_pipe_episode(self):
        assert self._matches("Colours and Shapes", "Ms Rachel | Colours and Shapes")

    def test_episode_pipe_show(self):
        assert self._matches("Colours and Shapes", "Colours and Shapes | Ms Rachel")

    # --- Space handling ---

    def test_multiple_spaces_in_source(self):
        assert self._matches("Hello   World", "Hello World")

    def test_zero_spaces_between_words(self):
        assert self._matches("Learn With Ms Rachel", "LearnWithMsRachel")

    # --- Punctuation: present in source, absent in candidate ---

    def test_source_comma_candidate_no_comma(self):
        assert self._matches("Hello, World", "Hello World")

    def test_source_apostrophe_candidate_no_apostrophe(self):
        assert self._matches("Baby's Day", "Babys Day")

    def test_source_exclamation_candidate_no_exclamation(self):
        assert self._matches("Wow! Great", "Wow Great")

    def test_source_period_candidate_no_period(self):
        assert self._matches("Dr. Seuss", "Dr Seuss")

    def test_source_question_candidate_no_question(self):
        assert self._matches("What is it?", "What is it")

    def test_source_colon_candidate_no_colon(self):
        assert self._matches("Part 1: Beginning", "Part 1 Beginning")

    # --- Punctuation: present in candidate, absent in source ---

    def test_candidate_comma_source_no_comma(self):
        assert self._matches("Hello World", "Hello, World")

    def test_candidate_exclamation_source_no_exclamation(self):
        assert self._matches("Wow Great", "Wow! Great")

    def test_candidate_period_source_no_period(self):
        assert self._matches("Dr Seuss", "Dr. Seuss")

    # --- Unicode quote normalisation ---

    def test_left_single_quote_stripped(self):
        assert self._matches("\u2018Hello\u2019", "Hello")

    def test_curly_apostrophe_normalised(self):
        assert self._matches("Baby\u2019s Day", "Baby's Day")

    def test_left_double_quote_stripped(self):
        assert self._matches("\u201cHello\u201d", "Hello")

    # --- AND / & interchangeability ---

    def test_and_matches_ampersand(self):
        assert self._matches("Songs and Games", "Songs & Games")

    def test_and_matches_uppercase_and(self):
        assert self._matches("Songs and Games", "Songs AND Games")

    def test_uppercase_and_matches_ampersand(self):
        assert self._matches("Songs AND Games", "Songs & Games")

    # --- Possessive apostrophe (source has apostrophe) ---

    def test_possessive_straight_apostrophe(self):
        assert self._matches("Baby's World", "Baby's World")

    def test_possessive_curly_apostrophe(self):
        assert self._matches("Baby's World", "Baby\u2019s World")

    def test_possessive_no_apostrophe_in_candidate(self):
        assert self._matches("Baby's World", "Babys World")

    # --- Parentheses optional ---

    def test_parentheses_optional(self):
        assert self._matches("Hello (World)", "Hello World")


# ---------------------------------------------------------------------------
# find_best_match_index
# ---------------------------------------------------------------------------

class TestFindBestMatchIndex:

    # --- Empty input ---

    def test_empty_list_returns_minus_one(self):
        assert find_best_match_index([], 'anything') == -1

    # --- Exact and obvious matches ---

    def test_exact_match(self):
        titles = ['some other show', 'learn with ms rachel - colours', 'another show']
        assert find_best_match_index(titles, 'learn with ms rachel - colours') == 1

    def test_single_entry_always_returned(self):
        assert find_best_match_index(['only one video'], 'completely different') == 0

    # --- Case insensitivity ---

    def test_case_insensitive_uppercase_titles(self):
        titles = ['LEARN WITH MS RACHEL', 'peppa pig']
        assert find_best_match_index(titles, 'learn with ms rachel') == 0

    def test_case_insensitive_uppercase_name(self):
        titles = ['learn with ms rachel', 'peppa pig']
        assert find_best_match_index(titles, 'LEARN WITH MS RACHEL') == 0

    # --- Fuzzy selection ---

    def test_closest_match_wins(self):
        titles = [
            'ms rachel colours and shapes for toddlers',
            'ms rachel counting to ten',
            'peppa pig season 1',
        ]
        assert find_best_match_index(titles, 'ms rachel - colours and shapes') == 0

    def test_series_episode_format(self):
        titles = [
            'ms rachel - friendship skills - videos for kids',
            'ms rachel - colours and shapes',
            'ms rachel - counting to 10',
        ]
        assert find_best_match_index(titles, 'ms rachel - friendship skills') == 0

    def test_longer_playlist_correct_entry(self):
        titles = [
            'ms rachel - abc song for babies',
            'ms rachel - counting 1 to 10',
            'ms rachel - colours and shapes for toddlers',
            'ms rachel - animal sounds',
            'ms rachel - bath time songs',
        ]
        assert find_best_match_index(titles, 'ms rachel - colours and shapes') == 2

    def test_duplicate_titles_returns_first(self):
        titles = ['ms rachel - colours', 'ms rachel - colours']
        assert find_best_match_index(titles, 'ms rachel - colours') == 0

    def test_unicode_titles(self):
        titles = ['canci\u00f3n de los colores', 'learn colours with ms rachel']
        assert find_best_match_index(titles, 'learn colours with ms rachel') == 1

    def test_punctuation_variant_matches_best(self):
        titles = ["baby's day out - songs", "completely unrelated video title here"]
        assert find_best_match_index(titles, "babys day out - songs") == 0


# ---------------------------------------------------------------------------
# offsethandler
# ---------------------------------------------------------------------------

class TestOffsethandler:

    def test_days_offset(self):
        base = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert offsethandler(base, {'days': '3'}) == datetime.datetime(2024, 1, 4, 12, 0, 0)

    def test_weeks_offset(self):
        base = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert offsethandler(base, {'weeks': '1'}) == datetime.datetime(2024, 1, 8, 12, 0, 0)

    def test_hours_offset(self):
        base = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert offsethandler(base, {'hours': '6'}) == datetime.datetime(2024, 1, 1, 18, 0, 0)

    def test_minutes_offset(self):
        base = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert offsethandler(base, {'minutes': '30'}) == datetime.datetime(2024, 1, 1, 12, 30, 0)

    def test_combined_offset(self):
        base = datetime.datetime(2024, 1, 1, 0, 0, 0)
        assert offsethandler(base, {'days': '1', 'hours': '6', 'minutes': '30'}) == datetime.datetime(2024, 1, 2, 6, 30, 0)

    def test_negative_offset(self):
        base = datetime.datetime(2024, 1, 5, 12, 0, 0)
        assert offsethandler(base, {'days': '-3'}) == datetime.datetime(2024, 1, 2, 12, 0, 0)

    def test_empty_offset_unchanged(self):
        base = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert offsethandler(base, {}) == base

    def test_zero_offset_unchanged(self):
        base = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert offsethandler(base, {'days': '0', 'hours': '0'}) == base



# ---------------------------------------------------------------------------
# redact_sensitive
# ---------------------------------------------------------------------------

class TestRedactSensitive:

    # --- Dict: sensitive keys redacted ---

    def test_apikey_redacted(self):
        from utils import redact_sensitive
        result = redact_sensitive({'apikey': 'secret123', 'format': 'bestvideo'})
        assert result['apikey'] == '***REDACTED***'
        assert result['format'] == 'bestvideo'

    def test_api_key_underscore_redacted(self):
        from utils import redact_sensitive
        result = redact_sensitive({'api_key': 'secret123'})
        assert result['api_key'] == '***REDACTED***'

    def test_cookiefile_redacted(self):
        from utils import redact_sensitive
        result = redact_sensitive({'cookiefile': '/config/cookies.txt', 'quiet': True})
        assert result['cookiefile'] == '***REDACTED***'
        assert result['quiet'] is True

    def test_cookies_file_redacted(self):
        from utils import redact_sensitive
        assert redact_sensitive({'cookies_file': '/config/cookies.txt'})['cookies_file'] == '***REDACTED***'

    def test_password_redacted(self):
        from utils import redact_sensitive
        assert redact_sensitive({'password': 'hunter2'})['password'] == '***REDACTED***'

    def test_token_redacted(self):
        from utils import redact_sensitive
        assert redact_sensitive({'token': 'abc123'})['token'] == '***REDACTED***'

    def test_non_sensitive_keys_preserved(self):
        from utils import redact_sensitive
        data = {'format': 'bestvideo', 'quiet': True, 'noplaylist': True}
        assert redact_sensitive(data) == data

    def test_case_insensitive_key_matching(self):
        from utils import redact_sensitive
        assert redact_sensitive({'ApiKey': 'secret'})['ApiKey'] == '***REDACTED***'
        assert redact_sensitive({'APIKEY': 'secret'})['APIKEY'] == '***REDACTED***'

    # --- Dict: nested ---

    def test_nested_dict_sensitive_key_redacted(self):
        from utils import redact_sensitive
        result = redact_sensitive({
            'format': 'bestvideo',
            'extractor_args': {'youtubepot': {'token': 'secret'}}
        })
        assert result['extractor_args']['youtubepot']['token'] == '***REDACTED***'
        assert result['format'] == 'bestvideo'

    def test_nested_dict_non_sensitive_preserved(self):
        from utils import redact_sensitive
        result = redact_sensitive({
            'extractor_args': {'youtubepot': {'server_home': ['/root/bgutil']}}
        })
        assert result['extractor_args']['youtubepot']['server_home'] == ['/root/bgutil']

    # --- List ---

    def test_list_of_dicts(self):
        from utils import redact_sensitive
        result = redact_sensitive([
            {'apikey': 'secret', 'format': 'best'},
            {'format': 'worst'},
        ])
        assert result[0]['apikey'] == '***REDACTED***'
        assert result[0]['format'] == 'best'
        assert result[1]['format'] == 'worst'

    def test_list_of_strings_preserved(self):
        from utils import redact_sensitive
        assert redact_sensitive(['bestvideo', 'bestaudio']) == ['bestvideo', 'bestaudio']

    # --- String ---

    def test_apikey_in_url_redacted(self):
        from utils import redact_sensitive
        url = 'http://sonarr:8989/api?apikey=mysecretkey&seriesId=1'
        result = redact_sensitive(url)
        assert '***REDACTED***' in result
        assert 'mysecretkey' not in result
        assert 'seriesId=1' in result

    def test_apikey_at_end_of_url(self):
        from utils import redact_sensitive
        url = 'http://sonarr:8989/api?seriesId=1&apikey=mysecretkey'
        assert 'mysecretkey' not in redact_sensitive(url)

    def test_plain_string_unchanged(self):
        from utils import redact_sensitive
        s = 'bestvideo+bestaudio/best'
        assert redact_sensitive(s) == s

    # --- Edge cases ---

    def test_empty_dict(self):
        from utils import redact_sensitive
        assert redact_sensitive({}) == {}

    def test_empty_list(self):
        from utils import redact_sensitive
        assert redact_sensitive([]) == []

    def test_empty_string(self):
        from utils import redact_sensitive
        assert redact_sensitive('') == ''

    def test_non_string_value_preserved(self):
        from utils import redact_sensitive
        assert redact_sensitive(42) == 42
        assert redact_sensitive(True) is True


# ---------------------------------------------------------------------------
# calculate_backoff
# ---------------------------------------------------------------------------

class TestCalculateBackoff:

    # --- First hit always returns base sleep ---

    def test_first_hit_returns_base_sleep(self):
        from utils import calculate_backoff
        assert calculate_backoff(1, 900, 2.0, 3600) == 900

    def test_zero_count_returns_base_sleep(self):
        from utils import calculate_backoff
        assert calculate_backoff(0, 900, 2.0, 3600) == 900

    # --- Exponential growth ---

    def test_second_hit_doubles(self):
        from utils import calculate_backoff
        assert calculate_backoff(2, 900, 2.0, 3600) == 1800

    def test_third_hit_quadruples(self):
        from utils import calculate_backoff
        assert calculate_backoff(3, 900, 2.0, 3600) == 3600

    def test_fourth_hit_capped_at_max(self):
        from utils import calculate_backoff
        # 900 * 2^3 = 7200, capped at 3600
        assert calculate_backoff(4, 900, 2.0, 3600) == 3600

    def test_custom_multiplier(self):
        from utils import calculate_backoff
        # 900 * 1.5^1 = 1350
        assert calculate_backoff(2, 900, 1.5, 3600) == 1350

    def test_multiplier_of_one_always_returns_base(self):
        from utils import calculate_backoff
        assert calculate_backoff(5, 900, 1.0, 3600) == 900

    # --- Max cap ---

    def test_never_exceeds_max_backoff(self):
        from utils import calculate_backoff
        assert calculate_backoff(100, 900, 2.0, 3600) == 3600

    def test_max_backoff_respected_with_small_base(self):
        from utils import calculate_backoff
        assert calculate_backoff(10, 60, 2.0, 300) == 300

    # --- Custom base sleep ---

    def test_custom_base_sleep(self):
        from utils import calculate_backoff
        assert calculate_backoff(1, 300, 2.0, 3600) == 300

    def test_custom_base_sleep_second_hit(self):
        from utils import calculate_backoff
        assert calculate_backoff(2, 300, 2.0, 3600) == 600


# ---------------------------------------------------------------------------
# is_rate_limit_error
# ---------------------------------------------------------------------------

class TestIsRateLimitError:

    # --- Should detect rate limit ---

    def test_rate_limited_hyphenated(self):
        from utils import is_rate_limit_error
        assert is_rate_limit_error('HTTP Error 429: rate-limited')

    def test_rate_limit_two_words(self):
        from utils import is_rate_limit_error
        assert is_rate_limit_error('rate limit exceeded')

    def test_try_again_later(self):
        from utils import is_rate_limit_error
        assert is_rate_limit_error('Please try again later')

    def test_case_insensitive_uppercase(self):
        from utils import is_rate_limit_error
        assert is_rate_limit_error('RATE LIMIT EXCEEDED')

    def test_case_insensitive_mixed(self):
        from utils import is_rate_limit_error
        assert is_rate_limit_error('You have been Rate-Limited')

    def test_embedded_in_longer_message(self):
        from utils import is_rate_limit_error
        assert is_rate_limit_error('yt-dlp error: HTTP 429 rate-limited by YouTube, try again later')

    # --- Should not detect as rate limit ---

    def test_video_unavailable(self):
        from utils import is_rate_limit_error
        assert not is_rate_limit_error('Video unavailable')

    def test_network_error(self):
        from utils import is_rate_limit_error
        assert not is_rate_limit_error('Network error: connection refused')

    def test_empty_string(self):
        from utils import is_rate_limit_error
        assert not is_rate_limit_error('')

    def test_unrelated_error(self):
        from utils import is_rate_limit_error
        assert not is_rate_limit_error('Unable to extract video data')


# ---------------------------------------------------------------------------
# YoutubeDLLogger
# ---------------------------------------------------------------------------

class TestYoutubeDLLogger:

    def setup_method(self):
        from utils import YoutubeDLLogger
        self.ydl_logger = YoutubeDLLogger()

    def test_info_delegates_to_logger(self):
        with patch('utils.logging.getLogger') as mock_get:
            from utils import YoutubeDLLogger
            logger = YoutubeDLLogger()
            logger.info('test info')
            mock_get.return_value.info.assert_called_once_with('test info')

    def test_debug_delegates_to_logger(self):
        with patch('utils.logging.getLogger') as mock_get:
            from utils import YoutubeDLLogger
            logger = YoutubeDLLogger()
            logger.debug('test debug')
            mock_get.return_value.debug.assert_called_once_with('test debug')

    def test_warning_delegates_to_logger(self):
        with patch('utils.logging.getLogger') as mock_get:
            from utils import YoutubeDLLogger
            logger = YoutubeDLLogger()
            logger.warning('test warning')
            mock_get.return_value.warning.assert_called_once_with('test warning')

    def test_error_delegates_to_logger(self):
        with patch('utils.logging.getLogger') as mock_get:
            from utils import YoutubeDLLogger
            logger = YoutubeDLLogger()
            logger.error('test error')
            mock_get.return_value.error.assert_called_once_with('test error')


# ---------------------------------------------------------------------------
# ytdl_hooks_debug
# ---------------------------------------------------------------------------

class TestYtdlHooksDebug:

    def test_finished_logs_filename(self):
        from utils import ytdl_hooks_debug
        d = {'status': 'finished', 'filename': '/sonarr_root/Ms Rachel/Season 1/episode.mkv'}
        with patch('utils.logging.getLogger') as mock_get:
            ytdl_hooks_debug(d)
        logged = mock_get.return_value.info.call_args[0][0]
        assert 'episode.mkv' in logged

    def test_downloading_logs_progress(self):
        from utils import ytdl_hooks_debug
        d = {
            'status': 'downloading',
            'filename': '/sonarr_root/episode.mkv',
            '_percent_str': '50%',
            '_eta_str': '30s',
        }
        with patch('utils.logging.getLogger') as mock_get:
            ytdl_hooks_debug(d)
        logged = mock_get.return_value.debug.call_args[0][0]
        assert '50%' in logged
        assert '30s' in logged

    def test_other_status_does_nothing(self):
        from utils import ytdl_hooks_debug
        d = {'status': 'error'}
        with patch('utils.logging.getLogger') as mock_get:
            ytdl_hooks_debug(d)
        mock_get.return_value.info.assert_not_called()
        mock_get.return_value.debug.assert_not_called()


# ---------------------------------------------------------------------------
# ytdl_hooks
# ---------------------------------------------------------------------------

class TestYtdlHooks:

    def test_finished_logs_filename(self):
        from utils import ytdl_hooks
        d = {'status': 'finished', 'filename': '/sonarr_root/Ms Rachel/Season 1/episode.mkv'}
        with patch('utils.logging.getLogger') as mock_get:
            ytdl_hooks(d)
        logged = mock_get.return_value.info.call_args[0][0]
        assert 'episode.mkv' in logged

    def test_other_status_does_nothing(self):
        from utils import ytdl_hooks
        d = {'status': 'downloading', 'filename': '/sonarr_root/episode.mkv'}
        with patch('utils.logging.getLogger') as mock_get:
            ytdl_hooks(d)
        mock_get.return_value.info.assert_not_called()