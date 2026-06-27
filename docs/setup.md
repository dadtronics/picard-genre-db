# Setup

The `python ...` commands below are identical on every OS. Only filesystem
paths differ — Windows examples use backslashes, Linux/macOS use forward
slashes.

## Create The Database

```bash
python bootstrap_db.py --db taxonomy.db
```

## Install The Picard Plugin

Picard's plugin folder depends on the OS:

| OS | Plugin folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\MusicBrainz\Picard\plugins\` |
| Linux | `~/.config/MusicBrainz/Picard/plugins/` |
| macOS | `~/Library/Preferences/MusicBrainz/Picard/plugins/` |

Install either the zip or the bare module into that folder:

```text
local_genre_db.zip
```

or:

```text
local_genre_db.py
```

For the zip install, `local_genre_db.py` must be at the top level of the zip.

Restart Picard after changing the installed plugin.

## Configure Taxonomy Paths

The plugin can read `taxonomy.db` directly if Picard's bundled Python includes
`sqlite3`. If not, it falls back to `taxonomy.json`.

Configure both paths. That gives you the best of both worlds.

Both config files are plain text placed **next to the installed plugin** (in the
plugin folder above), each containing the absolute path on its first line.

### SQLite DB Path

Create `taxonomy_path.txt` with the path to your `taxonomy.db`:

```text
# Windows
C:\path\to\picard-genre-db\taxonomy.db

# Linux / macOS
/home/you/picard-genre-db/taxonomy.db
```

### JSON Snapshot Path

Create `taxonomy_json_path.txt` with the path to your `taxonomy.json`:

```text
# Windows
C:\path\to\picard-genre-db\taxonomy.json

# Linux / macOS
/home/you/picard-genre-db/taxonomy.json
```

## Refresh The JSON Snapshot

If Picard is using SQLite successfully, this step is optional. If Picard is
falling back to JSON, refresh the snapshot any time you change decisions in
`taxonomy.db`:

```bash
python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

Then reload the album in Picard.

## Export Existing File Tags

Install Mutagen once:

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
