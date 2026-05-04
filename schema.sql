PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS canonical_genre (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS canonical_style (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    genre_id INTEGER NOT NULL,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    FOREIGN KEY (genre_id) REFERENCES canonical_genre(id)
);

CREATE TABLE IF NOT EXISTS alias_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL DEFAULT 'manual',
    raw_value TEXT NOT NULL COLLATE NOCASE,
    normalized_genre_id INTEGER,
    normalized_style_id INTEGER,
    notes TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    UNIQUE(source_name, raw_value),
    FOREIGN KEY (normalized_genre_id) REFERENCES canonical_genre(id),
    FOREIGN KEY (normalized_style_id) REFERENCES canonical_style(id)
);

CREATE TABLE IF NOT EXISTS style_alias_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_value TEXT NOT NULL UNIQUE COLLATE NOCASE,
    normalized_style_id INTEGER NOT NULL,
    notes TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    FOREIGN KEY (normalized_style_id) REFERENCES canonical_style(id)
);

CREATE TABLE IF NOT EXISTS artist_decision (
    artist_mbid TEXT PRIMARY KEY,
    normalized_genre_id INTEGER NOT NULL,
    genres_text TEXT NOT NULL DEFAULT '',
    styles_text TEXT NOT NULL DEFAULT '',
    reviewed INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (normalized_genre_id) REFERENCES canonical_genre(id)
);

CREATE TABLE IF NOT EXISTS release_decision (
    release_mbid TEXT PRIMARY KEY,
    normalized_genre_id INTEGER NOT NULL,
    genres_text TEXT NOT NULL DEFAULT '',
    styles_text TEXT NOT NULL DEFAULT '',
    reviewed INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (normalized_genre_id) REFERENCES canonical_genre(id)
);

CREATE TABLE IF NOT EXISTS release_group_decision (
    release_group_mbid TEXT PRIMARY KEY,
    normalized_genre_id INTEGER NOT NULL,
    genres_text TEXT NOT NULL DEFAULT '',
    styles_text TEXT NOT NULL DEFAULT '',
    reviewed INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (normalized_genre_id) REFERENCES canonical_genre(id)
);

CREATE TABLE IF NOT EXISTS recording_decision (
    recording_mbid TEXT PRIMARY KEY,
    normalized_genre_id INTEGER NOT NULL,
    genres_text TEXT NOT NULL DEFAULT '',
    styles_text TEXT NOT NULL DEFAULT '',
    reviewed INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (normalized_genre_id) REFERENCES canonical_genre(id)
);

CREATE TABLE IF NOT EXISTS raw_value_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_mbid TEXT,
    raw_value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS library_tag_import (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_source TEXT NOT NULL,
    file_path TEXT NOT NULL,
    title TEXT,
    artist TEXT,
    album TEXT,
    albumartist TEXT,
    date TEXT,
    raw_genre TEXT,
    raw_style TEXT,
    raw_grouping TEXT,
    raw_contentgroup TEXT,
    musicbrainz_artistid TEXT,
    musicbrainz_albumartistid TEXT,
    musicbrainz_releaseartistid TEXT,
    musicbrainz_albumid TEXT,
    musicbrainz_releasegroupid TEXT,
    musicbrainz_recordingid TEXT,
    musicbrainz_trackid TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(import_source, file_path)
);

CREATE TABLE IF NOT EXISTS plugin_run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    title TEXT,
    artist TEXT,
    album TEXT,
    recording_mbid TEXT,
    release_mbid TEXT,
    release_group_mbid TEXT,
    album_artist_mbids TEXT,
    track_artist_mbids TEXT,
    decision_source TEXT,
    decision_mbid TEXT,
    applied_genre TEXT,
    applied_styles TEXT,
    wrote_genre INTEGER NOT NULL DEFAULT 0,
    wrote_style INTEGER NOT NULL DEFAULT 0,
    wrote_contentgroup INTEGER NOT NULL DEFAULT 0,
    wrote_grouping INTEGER NOT NULL DEFAULT 0,
    seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alias_mapping_raw_value
    ON alias_mapping(raw_value);

CREATE INDEX IF NOT EXISTS idx_raw_value_log_lookup
    ON raw_value_log(source_name, entity_type, entity_mbid, value_type);

CREATE INDEX IF NOT EXISTS idx_library_tag_import_album
    ON library_tag_import(musicbrainz_albumid);

CREATE INDEX IF NOT EXISTS idx_library_tag_import_artist
    ON library_tag_import(musicbrainz_albumartistid);

CREATE INDEX IF NOT EXISTS idx_plugin_run_log_seen_at
    ON plugin_run_log(seen_at);
