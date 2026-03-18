import re
import os
import sys
import datetime
import yaml
import logging
from logging.handlers import RotatingFileHandler
from rapidfuzz import fuzz


CONFIGFILE = os.environ['CONFIGPATH']

_APOS = "(['\u2019]?)"  # optional apostrophe pattern, used by escapetitle


def redact_sensitive(data):
    """Redact sensitive information like API keys and cookie paths from log data.
    Safe to use on yt-dlp opts dicts before logging.

    - ``data``: dict, list, or str to redact

    returns:
        redacted copy of data
    """
    if isinstance(data, dict):
        sensitive_keys = ('apikey', 'api_key', 'cookie', 'cookies', 'cookiefile', 'cookies_file', 'password', 'token')
        return {
            k: '***REDACTED***' if any(s in k.lower() for s in sensitive_keys)
            else redact_sensitive(v) if isinstance(v, (dict, list))
            else v
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact_sensitive(item) for item in data]
    elif isinstance(data, str):
        data = re.sub(r'(apikey=)[^&\s]+', r'\1***REDACTED***', data)
        data = re.sub(r'(apikey["\']?\s*:\s*["\']?)[^&\s,}"\']+', r'\1***REDACTED***', data)
        return data
    return data

def escapetitle(string):
    """Escape string for use as a case-insensitive regex match pattern.
    Intended for matching episode titles against YouTube playlist entries.
    Uses re.IGNORECASE at the call site - do not uppercase here.

    - ``string``: string to manipulate

    returns:
        ``string``: str new string
    """
    # Normalise unicode quotes to their straight equivalents
    string = string.replace('\u2018', "'")   # left single quote -> straight
    string = string.replace('\u2019', "'")   # right single quote / curly apostrophe -> straight
    string = string.replace('\u201c', '"')   # left double quote -> straight
    string = string.replace('\u201d', '"')   # right double quote -> straight
    # Collapse multiple spaces to one
    string = re.sub(' +', ' ', string)
    # Escape regex special characters
    string = re.escape(string)
    # AND/& substitution - must happen before space conversion
    # After re.escape, spaces are '\\ ' so we target '\\ and\\ ' / '\\ AND\\ '
    string = re.sub(r'\\ (and|AND)\\ ', r'\\ (and|AND|&)\\ ', string)
    # Make double quotes optional (normalised above, still may appear)
    string = string.replace('"', '(["]*)')
    # Make parenthesis optional
    string = string.replace("\\(", "([\\(]?")
    string = string.replace("\\)", "[\\)]?)?")
    # Make source punctuation optional
    string = string.replace("'", _APOS)         # optional apostrophe (straight or curly)
    string = string.replace(",", "([,]?)")       # optional comma
    string = string.replace("!", "([!]?)")       # optional exclamation mark
    string = string.replace("\\.", "([\\.]?)")   # optional period
    string = string.replace("\\?", "([\\?]?)")  # optional question mark
    string = string.replace(":", "([:]?)")       # optional colon
    # Space conversion LAST - also allows optional punctuation before each gap
    # so candidates with extra punctuation the source title lacks still match
    string = string.replace('\\ ', "[\\.,!?'\u2019:]*[\\ ]*")
    return string


# Backwards compatibility alias - upperescape no longer uppercases.
# re.IGNORECASE is used at the call site instead.
upperescape = escapetitle


def find_best_match_index(titles, name):
    """Return the index of the best fuzzy match for name in titles.
    Both name and titles are lowercased before comparison so matching
    is case-insensitive regardless of how the caller normalises strings.
    Returns -1 if titles is empty.
    """
    best_match_index = -1
    best_match_score = -1
    name_lower = name.lower()
    for i, title in enumerate(titles):
        score = fuzz.ratio(name_lower, title.lower())
        if score > best_match_score:
            best_match_index = i
            best_match_score = score
    return best_match_index


def checkconfig():
    """Checks if config files exist in config path.
    If no config available, will copy template to config folder and exit script.

    returns:
        `cfg`: dict containing configuration values
    """
    logger = logging.getLogger('sonarr_youtubedl')
    config_template = os.path.abspath(CONFIGFILE + '.template')
    config_template_exists = os.path.exists(os.path.abspath(config_template))
    config_file = os.path.abspath(CONFIGFILE)
    config_file_exists = os.path.exists(os.path.abspath(config_file))
    if not config_file_exists:
        logger.critical('Configuration file not found.')
        if not config_template_exists:
            os.system('cp /app/config.yml.template ' + config_template)
        logger.critical("Create a config.yml using config.yml.template as an example.")
        sys.exit()
    else:
        logger.info('Configuration Found. Loading file.')
        with open(config_file, "r") as ymlfile:
            cfg = yaml.load(ymlfile, Loader=yaml.BaseLoader)
        return cfg


def offsethandler(airdate, offset):
    """Adjusts an episodes airdate.
    - ``airdate``: Airdate from sonarr (datetime)
    - ``offset``: Offset from series config.yml (dict)

    returns:
        ``airdate``: datetime updated original airdate
    """
    weeks = 0
    days = 0
    hours = 0
    minutes = 0
    if 'weeks' in offset:
        weeks = int(offset['weeks'])
    if 'days' in offset:
        days = int(offset['days'])
    if 'hours' in offset:
        hours = int(offset['hours'])
    if 'minutes' in offset:
        minutes = int(offset['minutes'])
    airdate = airdate + datetime.timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes)
    return airdate


class YoutubeDLLogger(object):

    def __init__(self):
        self.logger = logging.getLogger('sonarr_youtubedl')

    def info(self, msg: str) -> None:
        self.logger.info(msg)

    def debug(self, msg: str) -> None:
        self.logger.debug(msg)

    def warning(self, msg: str) -> None:
        self.logger.warning(msg)

    def error(self, msg: str) -> None:
        self.logger.error(msg)


def ytdl_hooks_debug(d):
    logger = logging.getLogger('sonarr_youtubedl')
    if d['status'] == 'finished':
        file_tuple = os.path.split(os.path.abspath(d['filename']))
        logger.info("      Done downloading {}".format(file_tuple[1]))
    if d['status'] == 'downloading':
        progress = "      {} - {} - {}".format(d['filename'], d['_percent_str'], d['_eta_str'])
        logger.debug(progress)


def ytdl_hooks(d):
    logger = logging.getLogger('sonarr_youtubedl')
    if d['status'] == 'finished':
        file_tuple = os.path.split(os.path.abspath(d['filename']))
        logger.info("      Downloaded - {}".format(file_tuple[1]))


def setup_logging(lf_enabled=True, lc_enabled=True, debugging=False):
    log_level = logging.DEBUG if debugging else logging.INFO
    logger = logging.getLogger('sonarr_youtubedl')
    logger.setLevel(log_level)
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    if lf_enabled:
        log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'sonarr_youtubedl.log')
        loggerfile = RotatingFileHandler(log_file, maxBytes=5000000, backupCount=5)
        loggerfile.setLevel(log_level)
        loggerfile.set_name('FileHandler')
        loggerfile.setFormatter(log_format)
        logger.addHandler(loggerfile)

    if lc_enabled:
        loggerconsole = logging.StreamHandler(sys.stdout)
        loggerconsole.setLevel(log_level)
        loggerconsole.set_name('StreamHandler')
        loggerconsole.setFormatter(log_format)
        logger.addHandler(loggerconsole)

    return logger