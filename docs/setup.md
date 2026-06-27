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
below from inside that folder. Python 3.9+ is required.

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

Copy `local_genre_db.py` (from `plugins/local_genre_db/` in your project folder)
into Picard's plugin folder:

| OS | Plugin folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\MusicBrainz\Picard\plugins\` |
| Linux | `~/.config/MusicBrainz/Picard/plugins/` |
| macOS | `~/Library/Preferences/MusicBrainz/Picard/plugins/` |

## 5. Point The Plugin At Your Data

The plugin now needs to find the `taxonomy.db` and `taxonomy.json` back in your
project folder. Create two small **pointer files** in Picard's plugin folder,
right next to `local_genre_db.py`. Each file holds a **single line: the absolute
path** to the real file — the plugin reads only that first line, and a leading
`~` is expanded to your home directory.

`taxonomy_path.txt` — points to your database. Its entire contents is one line:

```text
/home/you/picard-genre-db/taxonomy.db
```

`taxonomy_json_path.txt` — points to the snapshot. Its entire contents is one line:

```text
/home/you/picard-genre-db/taxonomy.json
```

On Windows that one line looks like `C:\path\to\picard-genre-db\taxonomy.json`
instead. Setting both lets the plugin read SQLite when available and fall back
to JSON otherwise.

> Tip: instead of these files, set the environment variables
> `PICARD_TAXONOMY_DB` and `PICARD_TAXONOMY_JSON` to the same paths. If set, they
> take precedence over the pointer files.

## 6. Start Picard

Restart Picard, then enable **Local Genre DB** under `Options -> Plugins`.
Reload an album to see normalized tags applied. Restart Picard again any time
you replace the installed plugin file.

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
