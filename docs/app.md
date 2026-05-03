# Local App

The local app is a small browser UI for day-to-day taxonomy curation.

It uses only Python's standard library and the existing SQLite database.

Start it from the project folder:

```powershell
python app.py
```

By default it opens:

```text
http://127.0.0.1:8686
```

If that port is busy, it picks the next available port and prints the URL.

## What It Does

- add or edit artist, album, exact-release, and track decisions
- review imported library tags and approve them as decisions
- add genres and styles
- auto-refresh `taxonomy.json` after saves
- show recent decisions
- keep the command-line workflow available as backup

## Scope Names

The app uses friendlier labels:

```text
Artist        -> artist decision
Album         -> release-group decision
Exact Release -> release decision
Track         -> recording decision
```

For most album pages, choose **Album**.

For artist pages, choose **Artist**.

For one-song overrides, choose **Track**.

## Import Review

Use **Imports** to turn scanned library tags into curated decisions.

The page groups rows from `library_tag_import` by source, scope, MBID, genre,
and grouping. You can edit the genre/grouping before approving.

Approving a row:

1. saves the matching decision to `taxonomy.db`
2. creates missing styles under the first genre
3. refreshes `taxonomy.json`

For old library tags, review a handful at a time. Avoid bulk-approving the
entire library until the candidates look clean.

## Run Without Opening A Browser

```powershell
python app.py --no-open
```

## Custom Port

```powershell
python app.py --port 8899
```
