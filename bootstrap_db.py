#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 rb303
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

STARTER_GENRES = [
    'Avant-Garde', 'Blues', 'Children\'s', 'Classical', 'Comedy/Spoken',
    'Country', 'Easy Listening', 'Electronic', 'Folk', 'Holiday',
    'International', 'Jazz', 'Latin', 'New Age', 'Pop/Rock', 'R&B',
    'Rap', 'Reggae', 'Religious', 'Stage & Screen', 'Vocal',
    'DJ Mix',
]

STARTER_STYLES = {
    'Electronic': [
        'Acid House', 'Breakbeat', 'Deep House', 'Electro', 'Garage House',
        'Hard House', 'House', 'Progressive House', 'Tech House', 'Techno',
        'Trance', 'UK Garage', 'Vocal House'
    ],
    'Rap': [
        'Boom Bap', 'East Coast Rap', 'Gangsta Rap', 'Hardcore Rap',
        'Southern Rap', 'West Coast Rap'
    ],
    'Pop/Rock': [
        'Alternative Rock', 'Dance-Pop', 'Indie Rock', 'New Wave',
        'Pop', 'Rock', 'Synthpop'
    ],
    'R&B': ['Contemporary R&B', 'Neo-Soul', 'Soul'],
    'Jazz': ['Acid Jazz', 'Bebop', 'Fusion', 'Smooth Jazz'],
}

STARTER_ALIASES = [
    ('musicbrainz', 'Hip-Hop', 'Rap', None, 'Normalize hyphenated hip-hop'),
    ('discogs', 'Hip Hop', 'Rap', None, 'Normalize hip hop'),
    ('manual', 'Club/Dance', 'Electronic', None, 'Treat as broad genre'),
    ('manual', 'Electronica', 'Electronic', None, 'Treat as broad genre'),
    ('manual', 'Deep House', 'Electronic', 'Deep House', 'Style alias'),
    ('manual', 'Garage House', 'Electronic', 'Garage House', 'Style alias'),
]


def load_schema(con: sqlite3.Connection, schema_path: Path) -> None:
    con.executescript(schema_path.read_text(encoding='utf-8'))


def get_genre_id(con: sqlite3.Connection, name: str) -> int:
    row = con.execute(
        'SELECT id FROM canonical_genre WHERE name = ?', (name,)
    ).fetchone()
    if not row:
        raise ValueError(f'Unknown genre: {name}')
    return int(row[0])


def get_style_id(con: sqlite3.Connection, name: str) -> int:
    row = con.execute(
        'SELECT id FROM canonical_style WHERE name = ?', (name,)
    ).fetchone()
    if not row:
        raise ValueError(f'Unknown style: {name}')
    return int(row[0])


def seed(con: sqlite3.Connection) -> None:
    for genre in STARTER_GENRES:
        con.execute(
            'INSERT OR IGNORE INTO canonical_genre(name) VALUES (?)',
            (genre,),
        )

    for genre, styles in STARTER_STYLES.items():
        genre_id = get_genre_id(con, genre)
        for style in styles:
            con.execute(
                'INSERT OR IGNORE INTO canonical_style(genre_id, name) VALUES (?, ?)',
                (genre_id, style),
            )

    for source_name, raw_value, genre_name, style_name, notes in STARTER_ALIASES:
        genre_id = get_genre_id(con, genre_name)
        style_id = get_style_id(con, style_name) if style_name else None
        con.execute(
            '''
            INSERT OR IGNORE INTO alias_mapping(
                source_name, raw_value, normalized_genre_id, normalized_style_id, notes
            ) VALUES (?, ?, ?, ?, ?)
            ''',
            (source_name, raw_value, genre_id, style_id, notes),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description='Create and seed taxonomy.db')
    parser.add_argument('--db', default='taxonomy.db', help='Path to SQLite DB')
    parser.add_argument(
        '--schema',
        default=str(Path(__file__).with_name('schema.sql')),
        help='Path to schema.sql',
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    schema_path = Path(args.schema)

    con = sqlite3.connect(db_path)
    try:
        load_schema(con, schema_path)
        seed(con)
        con.commit()
    finally:
        con.close()

    print(f'Initialized {db_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
