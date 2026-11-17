# Local Genre DB (Picard 3.0)

MusicBrainz Picard plugin that applies canonical `genre` and `grouping`
tags from a local taxonomy database, keyed by MusicBrainz IDs:

- Decisions by **release group**, **artist**, **release**, or
  **recording** MBID (release-group level first, then artist, release,
  recording).
- **Alias mapping**: raw genres/styles found in your files are mapped to
  canonical values.
- Unknown genres/styles can be logged as *pending decisions* for review.

Companion to the `picard-genre-db` project
(`<https://github.com/dadtronics/picard-genre-db>`), which provides
`manage_taxonomy.py` for building the taxonomy.

## Install (Picard 3.x)

Option A — let Picard do it (GUI: Options → Plugins → "Install from URL",
or CLI):

```
picard-cli plugins install https://github.com/dadtronics/picard-local-genre-db
```

Option B — clone into the plugins directory:

```
git clone https://github.com/dadtronics/picard-local-genre-db "%APPDATA%/MusicBrainz/Picard/plugins3/local_genre_db"
```

(Delete the `.git` folder inside afterwards if you like.)

## Point it at your taxonomy

The plugin looks for these files in its own folder first, then in the
plugins folder above it. **Put them in the plugins folder** (e.g.
`C:\Portable\Picard\MusicBrainz-Picard\Plugins\`): installing or updating
from GitHub replaces the plugin's own folder and would lose them.

- `taxonomy_path.txt` — absolute path to your `taxonomy.db`
  (preferred; requires a Python with `sqlite3` — Picard 3.x bundled
  Python has it).
- `taxonomy_json_path.txt` — absolute path to a `taxonomy.json`
  snapshot (fallback / safety net).

Example (create both files with a single absolute path each):

```
taxonomy_path.txt        ->  C:\Users\you\Projects\picard-genre-db\taxonomy.db
taxonomy_json_path.txt   ->  C:\Users\you\Projects\picard-genre-db\taxonomy.json
```

## Notes

- Logs to `local_genre_db_load.log` in its own folder. Lines saying
  `taxonomy_missing` mean the path files weren't found.
- Lookups read the DB fresh each time, but Picard only runs the plugin when a
  release loads: after adding a decision, right-click the release → Refresh.
- Runs as album- and track-level metadata processors; changes are
  in-memory until you save the tags.

## License

GPL-2.0-or-later. See `LICENSE` (full text in the companion project).
