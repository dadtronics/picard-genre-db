# Setup

## Create The Database

```powershell
python bootstrap_db.py --db taxonomy.db
```

## Install The Picard Plugin

Typical installed Picard plugin folder:

```text
%LOCALAPPDATA%\MusicBrainz\Picard\plugins\
```

Install either:

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

### SQLite DB Path

The installed plugin should read:

```text
path\to\picard-genre-db\taxonomy.db
```

Create this file next to the installed plugin:

```text
taxonomy_path.txt
```

Put this as the first line:

```text
path\to\picard-genre-db\taxonomy.db
```

### JSON Snapshot Path

The installed plugin should read:

```text
path\to\picard-genre-db\taxonomy.json
```

Create this file next to the installed plugin:

```text
taxonomy_json_path.txt
```

Put this as the first line:

```text
path\to\picard-genre-db\taxonomy.json
```

## Refresh The JSON Snapshot

If Picard is using SQLite successfully, this step is optional. If Picard is
falling back to JSON, refresh the snapshot any time you change decisions in
`taxonomy.db`:

```powershell
python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

Then reload the album in Picard.

## Export Existing File Tags

Install Mutagen once:

```powershell
python -m pip install mutagen
```

Scan a library or test folder:

```powershell
python export_library_tags.py --music-dir "D:\Music" --out imports/library_export.csv
```

Import the scan as staging data:

```powershell
python manage_taxonomy.py --db taxonomy.db import-library-csv imports/library_export.csv --source library_export --replace
```
