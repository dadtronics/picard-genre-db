# AGENTS.md

Guidance for AI coding agents (and humans) working in this repo. Keep changes
consistent with the conventions below.

## What this is

A local genre/style taxonomy for MusicBrainz Picard:

- `manage_taxonomy.py` — CLI + shared library (normalization, DB access, decisions).
- `app.py` — local web UI (stdlib `http.server`), imports `manage_taxonomy`.
- `plugins/local_genre_db/` — the Picard plugin (runs inside Picard).
- `export_library_tags.py` — scans audio files to CSV (needs `mutagen`).
- `bootstrap_db.py` — seeds a fresh DB with starter vocabulary.
- `schema.sql` — the SQLite schema (source of truth; applied via `ensure_schema`).
- `docs/` — concepts, setup, commands, workflows, troubleshooting.

## Conventions

- **Stdlib only for the core.** `manage_taxonomy.py` and `app.py` must not add
  runtime dependencies. Optional extras (`mutagen`) belong to a single script
  and are declared under `[project.optional-dependencies]`.
- **Quotes & style.** Single quotes throughout. `ruff` is configured to match
  (`quote-style = "single"`). Run `ruff check .` before finishing.
- **Errors.** Library/domain code raises `TaxonomyError` (not `SystemExit`) for
  bad input or unresolved lookups. Only the CLI's `main()` translates that into
  a process exit. The web layer catches it and shows/redirects an error.
- **Paths.** Default data-file paths come from `taxonomy.default_path(name)` so
  the tools work from any working directory. Don't hardcode bare relative names
  as defaults; let flags override.
- **Value separator.** Semicolon (`;`) is the only multi-value separator for
  genres/styles. Commas/newlines are normalized to `;` via
  `normalize_manual_list_text`. Slashes are literal text unless mapped.
- **Schema.** Change `schema.sql` for new tables/columns; add backfills in
  `ensure_schema`/`ensure_column` for existing databases. SQL values are always
  parameterized; only validated constants are interpolated into SQL strings.
- **Web schema init.** `init_schema()` runs once at startup — do not move schema
  setup back into the per-request path.

## Dev workflow

```bash
python -m pip install -e ".[dev]"   # ruff + pytest
ruff check .                        # lint (must pass)
pytest -q                           # tests live in tests/
```

- Tests use an in-memory SQLite DB seeded by the `con` fixture in
  `tests/conftest.py`. Prefer testing the pure helpers and decision round-trips
  there rather than spinning up the web server.
- CI (`.github/workflows/ci.yml`) runs `ruff check` + `pytest` on 3.9 and 3.12;
  keep both green.

## Gotchas

- The Picard plugin is excluded from linting (it relies on Picard-provided
  globals) and is not import-safe outside Picard.
- `*.db`, `taxonomy.json`, and scan/export outputs are gitignored runtime data —
  don't commit them.
