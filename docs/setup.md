# Setup

A first-time, start-to-finish setup. Do the steps in order.

The `python ...` commands are identical on every OS; only file paths differ
(Windows uses backslashes, Linux/macOS forward slashes).

## How It Fits Together

Two separate locations are involved, and that is the key to every step below:

- **Your project folder** — where you cloned/downloaded this repo. Your data
  lives here: `taxonomy.db` (the database) and `taxonomy.json` (a snapshot of
  it). You edit it with the CLI (`manage_taxonomy.py`) or the web UI (`app.py`).
- **Picard's plugin folder** — a different location, inside Picard, where the
  plugin file gets installed.

Because the plugin is installed away from your project folder, the final step is
to **point the plugin back at your data** using two tiny text files. Everything
before that exists to set up the data the plugin will read.

Below, "project folder" means the folder containing this repo, e.g.
`C:\path\to\picard-genre-db` or `/home/you/picard-genre-db`.

## 1. Get The Project

Clone or download this repository into a folder you intend to keep — moving it
later means updating the pointer files from step 5. Run every `python` command
below from inside that folder. Python 3.14+ is required.

## 2. Create The Database

```bash
python bootstrap_db.py --db taxonomy.db
```

Creates `taxonomy.db` in your project folder, seeded with starter genres,
styles, and aliases.

## 3. Create The JSON Snapshot

```bash
python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

Writes `taxonomy.json` next to the database. The plugin uses it as a fallback
when Picard's bundled Python has no `sqlite3`.

## 4. Install The Picard Plugin

The plugin lives in its own repository: [picard-local-genre-db](https://github.com/dadtronics/picard-local-genre-db).
In Picard 3: **Options -> Plugins -> Install from URL**, enter

```text
https://github.com/dadtronics/picard-local-genre-db
```

and pick the newest `vX.Y.Z` tag in the version selector (not `main`), so
Picard offers updates when new versions are tagged. Enable **Local Genre DB**.

## 5. Point The Plugin At Your Data

**Options -> Plugins -> Local Genre DB**: browse to `taxonomy.db` (and
optionally `taxonomy.json`). The status line confirms what was found, e.g.
`287 release groups, 37 aliases`. The setting is stored in Picard's config, so
plugin updates keep it.

Older setups that use the `PICARD_TAXONOMY_DB` / `PICARD_TAXONOMY_JSON`
environment variables or `taxonomy_path.txt` / `taxonomy_json_path.txt` pointer
files in Picard's Plugins folder keep working when the setting is empty.

## 6. Try It

Load an album you have a decision for. After editing decisions in the web app,
right-click the album -> **Refresh**; no Picard restart is needed.

## Keeping The JSON Snapshot Fresh

If Picard reads SQLite directly, this is optional. If it falls back to JSON,
re-export the snapshot whenever you change decisions in `taxonomy.db`:

```bash
python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

Then reload the album in Picard. (The web UI refreshes `taxonomy.json` for you
automatically on every save.)

## Optional: Export Existing File Tags

To seed decisions from tags already in your library, install Mutagen once:

```bash
python -m pip install mutagen
```

Scan a library or test folder:

```bash
# Windows
python export_library_tags.py --music-dir "D:\Music" --out imports/library_export.csv

# Linux / macOS
python export_library_tags.py --music-dir ~/Music --out imports/library_export.csv
```

Import the scan as staging data:

```bash
python manage_taxonomy.py --db taxonomy.db import-library-csv imports/library_export.csv --source library_export --replace
```
