#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable


def connect(db: str) -> sqlite3.Connection:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    return con


def get_genre_id(con: sqlite3.Connection, name: str) -> int:
    row = con.execute(
        'SELECT id FROM canonical_genre WHERE name = ?', (name,)
    ).fetchone()
    if not row:
        raise SystemExit(f'Unknown genre: {name}')
    return int(row['id'])


def get_style_id(con: sqlite3.Connection, name: str) -> int:
    row = con.execute(
        'SELECT id FROM canonical_style WHERE name = ?', (name,)
    ).fetchone()
    if not row:
        raise SystemExit(f'Unknown style: {name}')
    return int(row['id'])


def split_styles(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.split(';')]
    return [p for p in parts if p]


def add_genre(con: sqlite3.Connection, name: str) -> None:
    con.execute('INSERT OR IGNORE INTO canonical_genre(name) VALUES (?)', (name,))
    con.commit()
    print(f'Genre ensured: {name}')


def add_style(con: sqlite3.Connection, genre: str, style: str) -> None:
    genre_id = get_genre_id(con, genre)
    con.execute(
        'INSERT OR IGNORE INTO canonical_style(genre_id, name) VALUES (?, ?)',
        (genre_id, style),
    )
    con.commit()
    print(f'Style ensured: {style} -> {genre}')


def add_alias(
    con: sqlite3.Connection,
    source: str,
    raw: str,
    genre: str | None,
    style: str | None,
    notes: str | None,
    confidence: float,
) -> None:
    genre_id = get_genre_id(con, genre) if genre else None
    style_id = get_style_id(con, style) if style else None
    con.execute(
        '''
        INSERT INTO alias_mapping(
            source_name, raw_value, normalized_genre_id, normalized_style_id, notes, confidence
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_name, raw_value) DO UPDATE SET
            normalized_genre_id=excluded.normalized_genre_id,
            normalized_style_id=excluded.normalized_style_id,
            notes=excluded.notes,
            confidence=excluded.confidence
        ''',
        (source, raw, genre_id, style_id, notes, confidence),
    )
    con.commit()
    print(f'Alias mapped: [{source}] {raw}')


def decide_release_group(
    con: sqlite3.Connection,
    release_group_mbid: str,
    genre: str,
    styles: str,
    notes: str | None,
    locked: bool,
) -> None:
    genre_id = get_genre_id(con, genre)
    for style in split_styles(styles):
        get_style_id(con, style)
    con.execute(
        '''
        INSERT INTO release_group_decision(
            release_group_mbid, normalized_genre_id, styles_text, notes, locked
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(release_group_mbid) DO UPDATE SET
            normalized_genre_id=excluded.normalized_genre_id,
            styles_text=excluded.styles_text,
            notes=excluded.notes,
            locked=excluded.locked,
            updated_at=CURRENT_TIMESTAMP
        ''',
        (release_group_mbid, genre_id, styles, notes, int(locked)),
    )
    con.commit()
    print(f'Release-group decision saved: {release_group_mbid}')


def decide_recording(
    con: sqlite3.Connection,
    recording_mbid: str,
    genre: str,
    styles: str,
    notes: str | None,
    locked: bool,
) -> None:
    genre_id = get_genre_id(con, genre)
    for style in split_styles(styles):
        get_style_id(con, style)
    con.execute(
        '''
        INSERT INTO recording_decision(
            recording_mbid, normalized_genre_id, styles_text, notes, locked
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(recording_mbid) DO UPDATE SET
            normalized_genre_id=excluded.normalized_genre_id,
            styles_text=excluded.styles_text,
            notes=excluded.notes,
            locked=excluded.locked,
            updated_at=CURRENT_TIMESTAMP
        ''',
        (recording_mbid, genre_id, styles, notes, int(locked)),
    )
    con.commit()
    print(f'Recording decision saved: {recording_mbid}')


def list_table(con: sqlite3.Connection, sql: str, params: Iterable[object] = ()) -> None:
    rows = con.execute(sql, tuple(params)).fetchall()
    if not rows:
        print('No rows.')
        return
    for row in rows:
        print(dict(row))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Manage local taxonomy DB')
    parser.add_argument('--db', default='taxonomy.db', help='Path to SQLite DB')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('add-genre')
    p.add_argument('name')

    p = sub.add_parser('add-style')
    p.add_argument('genre')
    p.add_argument('style')

    p = sub.add_parser('add-alias')
    p.add_argument('--source', required=True)
    p.add_argument('--raw', required=True)
    p.add_argument('--genre')
    p.add_argument('--style')
    p.add_argument('--notes')
    p.add_argument('--confidence', type=float, default=1.0)

    p = sub.add_parser('decide-release-group')
    p.add_argument('--release-group-mbid', required=True)
    p.add_argument('--genre', required=True)
    p.add_argument('--styles', default='')
    p.add_argument('--notes')
    p.add_argument('--locked', action='store_true', default=False)

    p = sub.add_parser('decide-recording')
    p.add_argument('--recording-mbid', required=True)
    p.add_argument('--genre', required=True)
    p.add_argument('--styles', default='')
    p.add_argument('--notes')
    p.add_argument('--locked', action='store_true', default=False)

    sub.add_parser('list-genres')
    sub.add_parser('list-styles')
    sub.add_parser('list-aliases')
    sub.add_parser('list-release-decisions')
    sub.add_parser('list-recording-decisions')

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    con = connect(args.db)
    try:
        if args.command == 'add-genre':
            add_genre(con, args.name)
        elif args.command == 'add-style':
            add_style(con, args.genre, args.style)
        elif args.command == 'add-alias':
            add_alias(con, args.source, args.raw, args.genre, args.style, args.notes, args.confidence)
        elif args.command == 'decide-release-group':
            decide_release_group(
                con,
                args.release_group_mbid,
                args.genre,
                args.styles,
                args.notes,
                args.locked,
            )
        elif args.command == 'decide-recording':
            decide_recording(
                con,
                args.recording_mbid,
                args.genre,
                args.styles,
                args.notes,
                args.locked,
            )
        elif args.command == 'list-genres':
            list_table(con, 'SELECT id, name FROM canonical_genre ORDER BY name')
        elif args.command == 'list-styles':
            list_table(
                con,
                '''
                SELECT cs.id, cg.name AS genre, cs.name AS style
                FROM canonical_style cs
                JOIN canonical_genre cg ON cg.id = cs.genre_id
                ORDER BY cg.name, cs.name
                ''',
            )
        elif args.command == 'list-aliases':
            list_table(
                con,
                '''
                SELECT am.id, am.source_name, am.raw_value,
                       cg.name AS genre, cs.name AS style,
                       am.confidence, am.notes
                FROM alias_mapping am
                LEFT JOIN canonical_genre cg ON cg.id = am.normalized_genre_id
                LEFT JOIN canonical_style cs ON cs.id = am.normalized_style_id
                ORDER BY am.source_name, am.raw_value
                ''',
            )
        elif args.command == 'list-release-decisions':
            list_table(con, 'SELECT * FROM release_group_decision ORDER BY updated_at DESC')
        elif args.command == 'list-recording-decisions':
            list_table(con, 'SELECT * FROM recording_decision ORDER BY updated_at DESC')
        else:
            parser.error('Unknown command')
    finally:
        con.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
