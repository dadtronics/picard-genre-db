# Commands

This page is a command cookbook. For normal editing, use the local app first.

## Start The App

```bash
python app.py
```

Default URL:

```text
http://127.0.0.1:8686
```

Use the app for:

- adding and editing decisions
- reviewing imports
- cleaning suspicious vocabulary
- refreshing `taxonomy.json 
## Scan And Import A Library

Scan tags into CSV:

```bash
python export_library_tags.py --music-dir "D:\Music" --out imports/library_export.csv
```

Import the CSV into the staging table:

```bash
python manage_taxonomy.py --db taxonomy.db import-library-csv imports/library_export.csv --source library_export --replace
```

Then review in the app:

```text
http://127.0.0.1:8686/imports
```

## Audit Imported Tags

Summary:

```bash
python manage_taxonomy.py --db taxonomy.db list-import-summary --source library_export --limit 25
```

Invalid or unexpected genres:

```bash
python manage_taxonomy.py --db taxonomy.db list-import-genres --source library_export --only-invalid --limit 100
```

Raw grouping/style values:

```bash
python manage_taxonomy.py --db taxonomy.db list-import-styles --source library_export --limit 100
```

Likely duplicate style spellings:

```bash
python manage_taxonomy.py --db taxonomy.db list-import-style-clusters --source library_export --limit 100
```

Legacy `contentgroup` cases:

```bash
python manage_taxonomy.py --db taxonomy.db list-import-contentgroups --source library_export --limit 100
```

Statuses:

- `contentgroup_only`: file has contentgroup but no grouping
- `duplicate`: contentgroup and grouping match
- `conflict`: both exist and differ

## Refresh Picard Runtime JSON

Use this after CLI changes. The app refreshes JSON automatically after saves.

```bash
python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

## Add Decisions From CLI

Prefer the app unless batch work is faster.

Artist default:

```bash
python manage_taxonomy.py --db taxonomy.db decide-artist --artist-mbid "ARTIST_MBID" --genre "Electronic" --styles "House; Techno"
```

Release group default:

```bash
python manage_taxonomy.py --db taxonomy.db decide-release-group --release-group-mbid "RELEASE_GROUP_MBID" --genre "Electronic" --styles "Big Beat; Club/Dance; House"
```

Exact release:

```bash
python manage_taxonomy.py --db taxonomy.db decide-release --release-mbid "RELEASE_MBID" --genre "Stage & Screen; Pop/Rock" --styles "Soundtracks; Alternative Pop/Rock"
```

Track override:

```bash
python manage_taxonomy.py --db taxonomy.db decide-recording --recording-mbid "RECORDING_MBID" --genre "Rap" --styles "East Coast Rap"
```

## List Decisions

```bash
python manage_taxonomy.py --db taxonomy.db list-artist-decisions
python manage_taxonomy.py --db taxonomy.db list-release-group-decisions
python manage_taxonomy.py --db taxonomy.db list-release-decisions
python manage_taxonomy.py --db taxonomy.db list-recording-decisions
```

## Vocabulary

```bash
python manage_taxonomy.py --db taxonomy.db add-genre "Electronic"
python manage_taxonomy.py --db taxonomy.db add-style "Electronic" "Deep House"
python manage_taxonomy.py --db taxonomy.db list-genres
python manage_taxonomy.py --db taxonomy.db list-styles
```

For suspicious or combined styles, use the Vocabulary page in the app.

## Raw Value Mapping

Map a raw genre to a canonical genre and optional style:

```bash
python manage_taxonomy.py --db taxonomy.db map-raw-genre --raw "House" --genre "Electronic" --style "House"
```

Map a dirty style spelling to the style you want to keep:

```bash
python manage_taxonomy.py --db taxonomy.db map-raw-style --raw "Old School Rap" --genre "Rap" --style "Old-School Rap"
```

## Promote Imported Tags From CLI

The app import review is safer. Use CLI promotion only for controlled batches.

Preview:

```bash
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --limit 20
```

Apply:

```bash
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --apply
```

## Pending Decisions

These only work when the Picard plugin sees the values during metadata processing.

```bash
python manage_taxonomy.py --db taxonomy.db list-pending-decisions
python manage_taxonomy.py --db taxonomy.db import-pending-decisions
```

## Maintenance

Normalize decision text:

```bash
python manage_taxonomy.py --db taxonomy.db clean-decision-text
```

Inspect plugin run logs stored in the DB:

```bash
python manage_taxonomy.py --db taxonomy.db list-plugin-runs --limit 25
```

Clear plugin run logs:

```bash
python manage_taxonomy.py --db taxonomy.db clear-plugin-runs
```
