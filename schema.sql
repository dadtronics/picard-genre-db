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

CREATE TABLE IF NOT EXISTS release_group_decision (
    release_group_mbid TEXT PRIMARY KEY,
    normalized_genre_id INTEGER NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_alias_mapping_raw_value
    ON alias_mapping(raw_value);

CREATE INDEX IF NOT EXISTS idx_raw_value_log_lookup
    ON raw_value_log(source_name, entity_type, entity_mbid, value_type);
