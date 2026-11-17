# Troubleshooting

## Local Genre DB Is Not Listed In Picard

Install it from https://github.com/dadtronics/picard-local-genre-db (see setup step 4). Plugins installed while Picard runs
may need a restart before they show up in the list.

## Picard Plugin Loads But Does Nothing

1. In `Options -> Plugins`, make sure **Local Genre DB** is enabled.
2. Open `Options -> Plugins -> Local Genre DB` and check the status line. It
   must say `Using ...` with your decision counts, not `Not found`.
3. **Help -> View Debug/Error Log** shows which taxonomy the plugin loaded at
   startup and a warning for every lookup when it can't find one.
4. The plugin only runs when an album loads: right-click it -> **Refresh**.

## "Failed To Switch Ref ... Has Uncommitted Changes"

Plugin versions 0.4.0 and 0.4.1 wrote a log file inside the plugin's folder,
which blocks Picard's update. Uninstall Local Genre DB and install it again from
the URL, choosing the newest tag. Settings are kept.

## I Changed The DB But Picard Did Not Change

Right-click the album -> **Refresh**: the plugin re-reads `taxonomy.db` on every
lookup. If the status line says it is using `taxonomy.json` instead, refresh the
JSON snapshot:

```bash
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

```bash
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

```bash
python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

## Pending Decisions Are Empty

Manual edits typed after Picard loads metadata may not appear in the pending file.

Use the scan-and-promote workflow instead:

```bash
python export_library_tags.py --music-dir "D:\Music\Artist\Album" --out imports/picard_edit.csv
python manage_taxonomy.py --db taxonomy.db import-library-csv imports/picard_edit.csv --source picard_edit --replace
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --limit 20
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --apply
```
