# Commands

## Local App

```powershell
python app.py
```

The app is the easier path for normal decision editing. The commands below are
still useful for batch work and troubleshooting.

## Genres And Styles

```powershell
python manage_taxonomy.py --db taxonomy.db add-genre "Electronic"
python manage_taxonomy.py --db taxonomy.db add-style "Electronic" "Deep House"
python manage_taxonomy.py --db taxonomy.db list-genres
python manage_taxonomy.py --db taxonomy.db list-styles
```

## Decisions

Artist:

```powershell
python manage_taxonomy.py --db taxonomy.db decide-artist `
  --artist-mbid "ARTIST_MBID" `
  --genre "Electronic" `
  --styles "House"
```

Album default:

```powershell
python manage_taxonomy.py --db taxonomy.db decide-release-group `
  --release-group-mbid "RELEASE_GROUP_MBID" `
  --genre "Electronic" `
  --styles "Deep House; Garage House"
```

Exact release:

```powershell
python manage_taxonomy.py --db taxonomy.db decide-release `
  --release-mbid "RELEASE_MBID" `
  --genre "Electronic" `
  --styles "Deep House"
```

Track:

```powershell
python manage_taxonomy.py --db taxonomy.db decide-recording `
  --recording-mbid "RECORDING_MBID" `
  --genre "Rap" `
  --styles "East Coast Rap"
```

Multi-genre:

```powershell
python manage_taxonomy.py --db taxonomy.db decide-artist `
  --artist-mbid "ARTIST_MBID" `
  --genre "Pop/Rock; Reggae" `
  --styles "Contemporary Pop/Rock; Contemporary Reggae; Reggae-Pop"
```

## List Decisions

```powershell
python manage_taxonomy.py --db taxonomy.db list-artist-decisions
python manage_taxonomy.py --db taxonomy.db list-release-group-decisions
python manage_taxonomy.py --db taxonomy.db list-release-decisions
python manage_taxonomy.py --db taxonomy.db list-recording-decisions
```

## Import And Audit Library Tags

```powershell
python export_library_tags.py --music-dir "D:\Music" --out imports/library_export.csv
python manage_taxonomy.py --db taxonomy.db import-library-csv imports/library_export.csv --source library_export --replace
python manage_taxonomy.py --db taxonomy.db list-import-summary --source library_export --limit 25
python manage_taxonomy.py --db taxonomy.db list-import-genres --source library_export --only-invalid --limit 100
python manage_taxonomy.py --db taxonomy.db list-import-styles --source library_export --limit 100
python manage_taxonomy.py --db taxonomy.db list-import-style-clusters --source library_export --limit 100
python manage_taxonomy.py --db taxonomy.db list-import-contentgroups --source library_export --limit 100
```

## Promote Imported Tags

Preview:

```powershell
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --limit 20
```

Apply:

```powershell
python manage_taxonomy.py --db taxonomy.db promote-imported-decisions --source picard_edit --scope release_group --apply
```

## Pending Decisions

These only work when the plugin sees the values during metadata processing.

```powershell
python manage_taxonomy.py --db taxonomy.db list-pending-decisions
python manage_taxonomy.py --db taxonomy.db import-pending-decisions
```

## Refresh Picard JSON

```powershell
python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```
