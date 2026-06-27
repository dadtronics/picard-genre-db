# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Licensed the project under GPL-2.0-or-later (`LICENSE`, `pyproject.toml`
  metadata, and per-file SPDX headers).
- `pytest` suite covering text normalization, genre resolution, and decision
  persistence/export (`tests/`).
- `pyproject.toml` with optional `dev` (ruff + pytest) and `scan` (mutagen)
  dependency groups, plus ruff and pytest configuration.
- GitHub Actions CI running `ruff check` and `pytest` on Python 3.9 and 3.12.
- `AGENTS.md` documenting repo conventions; Development section in the README.

### Changed
- Library/domain code now raises `TaxonomyError` instead of `SystemExit`; the
  CLI translates it to a clean error message and exit code, and the web UI can
  surface it without killing the request.
- The web UI applies the database schema once at startup instead of on every
  request.
- Default database/JSON/pending paths now resolve relative to the script, so the
  CLI and web UI work from any working directory (flags still override).

### Security
- The web UI rejects cross-origin `POST` requests (CSRF) by checking the
  `Origin` header against `Host`.
