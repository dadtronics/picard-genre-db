# Picard Taxonomy Starter

Starter kit for using a **local SQLite genre/style taxonomy** from **MusicBrainz Picard**.

This is designed around your workflow:

1. **Mp3tag first** for cleanup only
2. **Picard second** for identity + MBIDs + normalized genre/style from your DB
3. **MusicBee third** for artwork and library management

## What this includes

- `schema.sql` — SQLite schema for canonical genres, styles, aliases, and release/track decisions
- `bootstrap_db.py` — creates `taxonomy.db` and seeds a small starter taxonomy
- `manage_taxonomy.py` — simple CLI to add genres, styles, aliases, and decisions
- `plugins/local_genre_db/local_genre_db.py` — Picard plugin that reads from the SQLite DB and writes normalized `genre` and `style`

## Recommended model

Picard should remain the **identifier writer**. The local DB should be the **taxonomy authority**.

The plugin works in this order:

1. Look for an explicit **recording decision** using track MBID
2. Fall back to an explicit **release-group decision** using release group MBID
3. Fall back to **release alias mapping** from raw values already present in metadata
4. Apply normalized values to Picard metadata:
   - `genre` = one canonical broad genre
   - `style` = semicolon-separated normalized styles

## Initial setup

Create the DB:

```bash
python bootstrap_db.py --db taxonomy.db
```

Install the Picard plugin by copying:

- `plugins/local_genre_db/local_genre_db.py`

into your Picard plugins directory.

Typical Windows Picard plugin location:

```text
%APPDATA%\MusicBrainz\Picard\plugins\
```

Create a subfolder named `local_genre_db`, then place the file inside it.

## Picard plugin configuration

Open Picard:

- Options -> Plugins -> enable **Local Genre DB**
- Options -> Plugins -> Local Genre DB
- Set the path to your `taxonomy.db`
- Optional: set whether the plugin should overwrite existing genre/style tags

## Basic usage

### Add a genre

```bash
python manage_taxonomy.py --db taxonomy.db add-genre "Electronic"
```

### Add a style under a genre

```bash
python manage_taxonomy.py --db taxonomy.db add-style "Electronic" "Deep House"
```

### Map a raw source term to your canonical values

```bash
python manage_taxonomy.py --db taxonomy.db add-alias \
  --source discogs \
  --raw "Club/Dance" \
  --genre "Electronic"
```

```bash
python manage_taxonomy.py --db taxonomy.db add-alias \
  --source musicbrainz \
  --raw "Hip-Hop" \
  --genre "Rap"
```

```bash
python manage_taxonomy.py --db taxonomy.db add-alias \
  --source manual \
  --raw "Garage House" \
  --genre "Electronic" \
  --style "Garage House"
```

### Add an explicit release-group decision

```bash
python manage_taxonomy.py --db taxonomy.db decide-release-group \
  --release-group-mbid 12345678-1234-1234-1234-123456789abc \
  --genre "Electronic" \
  --styles "Deep House;Garage House"
```

### Add an explicit recording decision

```bash
python manage_taxonomy.py --db taxonomy.db decide-recording \
  --recording-mbid abcdefab-1234-1234-1234-abcdefabcdef \
  --genre "Rap" \
  --styles "East Coast Rap"
```

## Notes

- This starter is intentionally conservative.
- Unknown values should be reviewed and mapped, not written blindly.
- You can later extend this with a review queue UI or CSV import/export.

## Future directions

Good next additions:

- import/export aliases from CSV
- review queue for unmapped raw terms
- batch scan of Picard-tagged files to pre-populate release-group decisions
- per-artist defaults
- lock flag so reviewed decisions are never auto-changed
