# Picard Genre DB

A local genre/style taxonomy for MusicBrainz Picard.

The short version:

1. Picard writes identity and MusicBrainz IDs.
2. `taxonomy.db` stores your canonical genres, styles, aliases, and decisions.
3. The Picard plugin can read `taxonomy.db` directly when Picard has `sqlite3`.
4. If Picard lacks `sqlite3`, the plugin falls back to `taxonomy.json`.
5. The Picard plugin writes normalized `genre` and `grouping`.

## Start Here

- [Concepts](docs/concepts.md) explains the mental model: canonical values vs decisions, and artist/album/track scope.
- [Setup](docs/setup.md) covers database setup, plugin install, and JSON snapshot configuration.
- [Workflows](docs/workflows.md) covers the common tagging/audit flows.
- [Local App](docs/app.md) covers the browser UI for day-to-day curation.
- [Commands](docs/commands.md) is a command reference.
- [Troubleshooting](docs/troubleshooting.md) covers Picard surprises like missing Grouping values.

## Current Defaults

- Semicolon (`;`) is the only multi-value separator.
- Commas and slashes are treated as literal text unless mapped explicitly.
- Explicit DB decisions overwrite Picard metadata by default; alias mappings only fill blanks.
- Picard tries `taxonomy.db` first when `sqlite3` is available, then falls back to `taxonomy.json`.
- `grouping` is the main style/grouping tag used for saved files.
- The app and DB store multiple values as semicolon-separated text; the Picard plugin writes them to Picard metadata as multi-value lists.

## Core Loop

Browser UI:

```powershell
python app.py
```

Command line:

```powershell
python manage_taxonomy.py --db taxonomy.db decide-release-group `
  --release-group-mbid "RELEASE_GROUP_MBID" `
  --genre "Electronic" `
  --styles "Electro-Techno; Techno; Club/Dance"

python manage_taxonomy.py --db taxonomy.db export-plugin-json --out taxonomy.json
```

Reload the album in Picard, confirm the New Value column looks right, then save.
