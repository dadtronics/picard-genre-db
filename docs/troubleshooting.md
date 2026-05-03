# Troubleshooting

## Local Genre DB Is Not Listed In Picard

For a zip install, make sure the zip contains `local_genre_db.py` at the top level.

Restart Picard after copying the plugin.

## Picard Plugin Loads But Does Nothing

In `Options -> Plugins`, make sure **Local Genre DB** is enabled. In Picard's
plugin list, grey means installed but inactive; green means active.

Check the load log:

```powershell
Get-Content "$env:LOCALAPPDATA\MusicBrainz\Picard\plugins\local_genre_db_load.log" -Tail 50
```

The log should show:

```text
db_path='path\\to\\picard-genre-db\\taxonomy.db' exists=True
json_path='path\\to\\picard-genre-db\\taxonomy.json' exists=True
snapshot_loaded ...
```

If the DB path points somewhere else, fix `taxonomy_path.txt`.

If the JSON path points somewhere else, fix `taxonomy_json_path.txt`.

## I Changed The DB But Picard Did Not Change

Refresh the JSON snapshot:

```powershell
python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

Then reload the album in Picard.

## Grouping Disappears In Picard's New Value Column

The plugin does not erase grouping by default. If there is no DB decision, it should do nothing.

Picard's tag table has two sides:

```text
Original Value = what is currently in the file
New Value = what Picard will save
```

If `Grouping` exists in Original Value but is blank in New Value, do not save until you know why. Saving can remove tags if Picard's current metadata does not include that field.

Check what is actually on disk by scanning the album folder:

```powershell
python export_library_tags.py --music-dir "D:\Music\Artist\Album" --out imports/check_album.csv
python manage_taxonomy.py --db taxonomy.db import-library-csv imports/check_album.csv --source check_album --replace
python manage_taxonomy.py --db taxonomy.db list-import-summary --source check_album --limit 50
```

If `with_grouping` is high, the tags still exist in the files.

If `with_grouping` is low, the files no longer have those grouping tags.

## Picard Cannot Import sqlite3

Some Picard builds do not include Python's compiled SQLite module. The plugin
will log this and fall back to `taxonomy.json`.

Use:

```powershell
python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

## Pending Decisions Are Empty

Manual edits typed after Picard loads metadata may not appear in the pending file.

Use the scan-and-promote workflow instead:

```powershell
python export_library_tags.py --music-dir "D:\Music\Artist\Album" --out imports/picard_edit.csv
python manage_taxonomy.py --db taxonomy.db import-library-csv imports/picard_edit.csv --source picard_edit --replace
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --limit 20
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --apply
```
