# Workflows

## Add An Album-Level AllMusic Decision

Use this when the source is an album, single, EP, or mix page.

```bash
python manage_taxonomy.py --db taxonomy.db decide-release-group --release-group-mbid "RELEASE_GROUP_MBID" --genre "Electronic" --styles "Electro-Techno; Techno; Club/Dance"

python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

Reload the album in Picard and confirm `Grouping` appears in the New Value column.

## Add An Artist-Level Decision

Use this when the source is an artist page.

```bash
python manage_taxonomy.py --db taxonomy.db decide-artist --artist-mbid "ARTIST_MBID" --genre "Electronic; Pop/Rock" --styles "Electro-Techno; Techno; Club/Dance; Alternative Pop/Rock; Alternative/Indie Rock"

python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

## Add A Track Override

Use this when one track should differ from the album default.

```bash
python manage_taxonomy.py --db taxonomy.db decide-recording --recording-mbid "RECORDING_MBID" --genre "Rap" --styles "East Coast Rap"

python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

## Promote Manually Saved Tags Into Decisions

Picard plugin metadata processors run while Picard loads metadata. If you type `Genre` and `Grouping` manually after load, the plugin may not see those edits as pending decisions.

For manual edits:

1. Save the tags in Picard.
2. Scan just that album/folder.
3. Import the scan as a temporary source.
4. Preview promotion.
5. Apply only if the preview looks right.

```bash
python export_library_tags.py --music-dir "D:\Music\Artist\Album" --out imports/picard_edit.csv
python manage_taxonomy.py --db taxonomy.db import-library-csv imports/picard_edit.csv --source picard_edit --replace
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --limit 20
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --apply
```

For compilations, mixes, and series releases, prefer `--scope release_group`.

Use `--scope artist` only when the tag values really describe the artist broadly.

## Audit Imported Genres

```bash
python manage_taxonomy.py --db taxonomy.db list-import-genres --source main_library --only-invalid --limit 100
```

## Audit Imported Styles

```bash
python manage_taxonomy.py --db taxonomy.db list-import-styles --source main_library --limit 100
```

## Find Likely Duplicate Style Spellings

```bash
python manage_taxonomy.py --db taxonomy.db list-import-style-clusters --source main_library --limit 100
```

## Map Dirty Raw Values

Map a raw genre to a canonical genre and optional style:

```bash
python manage_taxonomy.py --db taxonomy.db map-raw-genre --raw "House" --genre "Electronic" --style "House"
```

Map a dirty style spelling to the style you want to keep:

```bash
python manage_taxonomy.py --db taxonomy.db map-raw-style --raw "Old School Rap" --genre "Rap" --style "Old-School Rap"
```

