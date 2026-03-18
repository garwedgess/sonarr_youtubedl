# Changelog

## 1.0.0 (2026-03-18)


### Features

* add exponential backoff for YouTube rate limiting ([#4](https://github.com/garwedgess/sonarr_youtubedl/issues/4)) ([abd3187](https://github.com/garwedgess/sonarr_youtubedl/commit/abd3187fe41011d2ec63bdfb467b5ae4633b4cd0))
* add min_check_interval per series to throttle yt-dlp playlist scans ([a6e4a28](https://github.com/garwedgess/sonarr_youtubedl/commit/a6e4a2872964987faa3572e82c97be53220b4596))
* **docker:** add arm support ([65ec7c3](https://github.com/garwedgess/sonarr_youtubedl/commit/65ec7c3468b5817e550b9966031dc7ee2f54e4d8))
* **docker:** add arm support ([cc29380](https://github.com/garwedgess/sonarr_youtubedl/commit/cc2938010d9387ab793921d190198ae1b5cbe451))
* refactor architecture, staging import, notifications and search improvements ([#1](https://github.com/garwedgess/sonarr_youtubedl/issues/1)) ([f20f300](https://github.com/garwedgess/sonarr_youtubedl/commit/f20f300455ea6806fdeb52cd761d4664c11bf10e))


### Bug Fixes

* add PO token support for age-restricted and kids content ([5f1085e](https://github.com/garwedgess/sonarr_youtubedl/commit/5f1085eaecf4fc3e3ba2e13a273a0ed6ea056eb1))
* API timeouts, update_formats precedence and appendcookie return ([cb4bab6](https://github.com/garwedgess/sonarr_youtubedl/commit/cb4bab69d3436d780cb628227e4c07f9286806a3))
* Create files as current user based on PUID and PGID passed in environment variables so the files are created as the current user allowing sonarr to see them ([75425b6](https://github.com/garwedgess/sonarr_youtubedl/commit/75425b66b0f971f0dc947ae6ee1bd14f3743447a))
* improve path handling and Sonarr rescan reliability ([26ed188](https://github.com/garwedgess/sonarr_youtubedl/commit/26ed188b6ae41fc16edc1d5846e148f09d730cc6))
* output directory missing series title ([32e5c29](https://github.com/garwedgess/sonarr_youtubedl/commit/32e5c2944d731f47b60f0c2e9fdbe546d4d4a531))
* removed forward slashes from episode title which was breaking sonarr finding the file as it was in a different directory ([75425b6](https://github.com/garwedgess/sonarr_youtubedl/commit/75425b66b0f971f0dc947ae6ee1bd14f3743447a))
* Sonarr Config ([5f63299](https://github.com/garwedgess/sonarr_youtubedl/commit/5f63299f0e13b6370d05f12e09c006e64b1aa697))
