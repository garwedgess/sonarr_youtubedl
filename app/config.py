import logging
import os
import sys
import yaml

logger = logging.getLogger('sonarr_youtubedl')

CONFIGFILE = os.environ['CONFIGPATH']


def load_config():
    """Load config from CONFIGFILE. Copies template and exits if not found."""
    config_file = os.path.abspath(CONFIGFILE)
    config_template = os.path.abspath(CONFIGFILE + '.template')

    if not os.path.exists(config_file):
        logger.critical('Configuration file not found.')
        if not os.path.exists(config_template):
            os.system('cp /app/config.yml.template ' + config_template)
        logger.critical("Create a config.yml using config.yml.template as an example.")
        sys.exit()

    logger.info('Configuration found. Loading file.')
    with open(config_file, 'r') as f:
        return yaml.load(f, Loader=yaml.BaseLoader)


def validate_config(cfg):
    """Validate config values. Logs all errors then exits if any are found."""
    errors = []

    sonarr = cfg.get('sonarr', {})
    for field in ('host', 'port', 'apikey', 'ssl'):
        if not sonarr.get(field):
            errors.append(f"sonarr.{field} is required")
    if sonarr.get('port') and not str(sonarr['port']).isdigit():
        errors.append("sonarr.port must be an integer")
    if sonarr.get('ssl', '').lower() not in ('true', 'false'):
        errors.append("sonarr.ssl must be true or false")

    sonarrytdl = cfg.get('sonarrytdl', {})
    if not sonarrytdl.get('scan_interval'):
        errors.append("sonarrytdl.scan_interval is required")
    elif not str(sonarrytdl['scan_interval']).isdigit() or int(sonarrytdl['scan_interval']) < 1:
        errors.append("sonarrytdl.scan_interval must be a positive integer")

    series = cfg.get('series', [])
    if not series:
        errors.append("series list is empty — nothing to process")
    for i, ser in enumerate(series):
        if not ser.get('title'):
            errors.append(f"series[{i}] is missing required field 'title'")
        if not ser.get('url'):
            errors.append(f"series[{i}] is missing required field 'url'")

    telegram = cfg.get('telegram', {})
    if telegram:
        has_token = bool(telegram.get('bot_token'))
        has_chat = bool(telegram.get('chat_id'))
        if has_token and not has_chat:
            errors.append("telegram.bot_token is set but telegram.chat_id is missing")
        if has_chat and not has_token:
            errors.append("telegram.chat_id is set but telegram.bot_token is missing")

    if errors:
        for error in errors:
            logger.error(f"Config error: {error}")
        sys.exit("Exiting due to configuration errors")