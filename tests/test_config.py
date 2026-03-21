import os
import sys
import pytest
from unittest.mock import patch, mock_open, MagicMock

os.environ.setdefault('CONFIGPATH', '/config/config.yml')
sys.path.insert(0, os.path.dirname(__file__))

import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_cfg(**overrides):
    cfg = {
        'sonarrytdl': {'scan_interval': '60', 'debug': 'false'},
        'sonarr': {'host': 'localhost', 'port': '8989', 'apikey': 'testkey', 'ssl': 'false'},
        'series': [{'title': 'Ms Rachel', 'url': 'https://youtube.com/channel/msrachel'}],
    }
    cfg.update(overrides)
    return cfg


# ---------------------------------------------------------------------------
# TestLoadConfig
# ---------------------------------------------------------------------------

class TestLoadConfig:

    def test_returns_cfg_when_file_exists(self):
        yaml_content = "sonarr:\n  host: localhost\n"
        with patch('config.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=yaml_content)), \
             patch('config.yaml.load', return_value={'sonarr': {'host': 'localhost'}}):
            result = config.load_config()
        assert result == {'sonarr': {'host': 'localhost'}}

    def test_exits_when_config_missing(self):
        with patch('config.os.path.exists', return_value=False), \
             patch('config.os.system'), \
             pytest.raises(SystemExit):
            config.load_config()

    def test_copies_template_when_missing(self):
        with patch('config.os.path.exists', return_value=False), \
             patch('config.os.system') as mock_sys, \
             pytest.raises(SystemExit):
            config.load_config()
        mock_sys.assert_called_once()


# ---------------------------------------------------------------------------
# TestValidateConfig
# ---------------------------------------------------------------------------

class TestValidateConfig:

    def test_valid_config_does_not_raise(self):
        config.validate_config(make_cfg())

    def test_missing_sonarr_host_exits(self):
        cfg = make_cfg(sonarr={'port': '8989', 'apikey': 'key', 'ssl': 'false'})
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_missing_sonarr_apikey_exits(self):
        cfg = make_cfg(sonarr={'host': 'localhost', 'port': '8989', 'ssl': 'false'})
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_invalid_sonarr_port_exits(self):
        cfg = make_cfg(sonarr={'host': 'localhost', 'port': 'notanumber', 'apikey': 'key', 'ssl': 'false'})
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_invalid_sonarr_ssl_exits(self):
        cfg = make_cfg(sonarr={'host': 'localhost', 'port': '8989', 'apikey': 'key', 'ssl': 'maybe'})
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_missing_scan_interval_exits(self):
        cfg = make_cfg(sonarrytdl={'debug': 'false'})
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_zero_scan_interval_exits(self):
        cfg = make_cfg(sonarrytdl={'scan_interval': '0', 'debug': 'false'})
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_empty_series_exits(self):
        cfg = make_cfg(series=[])
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_series_missing_title_exits(self):
        cfg = make_cfg(series=[{'url': 'https://youtube.com/channel/msrachel'}])
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_series_missing_url_exits(self):
        cfg = make_cfg(series=[{'title': 'Ms Rachel'}])
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_telegram_token_without_chat_id_exits(self):
        cfg = make_cfg(telegram={'bot_token': 'abc123'})
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_telegram_chat_id_without_token_exits(self):
        cfg = make_cfg(telegram={'chat_id': '12345'})
        with pytest.raises(SystemExit):
            config.validate_config(cfg)

    def test_telegram_both_set_does_not_raise(self):
        cfg = make_cfg(telegram={'bot_token': 'abc123', 'chat_id': '12345'})
        config.validate_config(cfg)

    def test_multiple_errors_all_logged(self):
        cfg = make_cfg(
            sonarr={'host': '', 'port': 'bad', 'ssl': 'maybe'},
            series=[]
        )
        with patch('config.logger') as mock_log, pytest.raises(SystemExit):
            config.validate_config(cfg)
        assert mock_log.error.call_count >= 2