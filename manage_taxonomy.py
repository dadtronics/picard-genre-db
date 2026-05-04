#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Iterable


def connect(db: str) -> sqlite3.Connection:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    return con


def ensure_schema(con: sqlite3.Connection) -> None:
    schema_path = Path(__file__).with_name('schema.sql')
    con.executescript(schema_path.read_text(encoding='utf-8'))
    for table in (
        'artist_decision',
        'release_decision',
        'release_group_decision',
        'recording_decision',
    ):
        ensure_column(con, table, 'genres_text', "TEXT NOT NULL DEFAULT ''")
    ensure_column(con, 'library_tag_import', 'raw_contentgroup', 'TEXT')
    con.commit()


def ensure_column(
    con: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {
        str(row['name'])
        for row in con.execute(f'PRAGMA table_info({table})').fetchall()
    }
    if column not in columns:
        con.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def get_genre_id(con: sqlite3.Connection, name: str) -> int:
    name = sanitize_value(name)
    row = con.execute(
        'SELECT id FROM canonical_genre WHERE name = ?', (name,)
    ).fetchone()
    if not row:
        raise SystemExit(f'Unknown genre: {name}')
    return int(row['id'])


def normalize_genres(con: sqlite3.Connection, genres: str) -> tuple[int, str, str]:
    names = split_semicolon_values(genres)
    if not names:
        raise SystemExit('At least one genre is required.')
    genre_ids = [get_genre_id(con, name) for name in names]
    return genre_ids[0], names[0], '; '.join(names)


def get_style_id(con: sqlite3.Connection, name: str) -> int:
    name = sanitize_value(name)
    row = con.execute(
        'SELECT id FROM canonical_style WHERE name = ?', (name,)
    ).fetchone()
    if not row:
        raise SystemExit(f'Unknown style: {name}')
    return int(row['id'])


def split_semicolon_values(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [sanitize_value(p) for p in value.split(';')]
    return [p for p in parts if p]


def sanitize_value(value: str | None) -> str:
    if not value:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def normalize_semicolon_text(value: str | None) -> str:
    return '; '.join(split_semicolon_values(value))


def normalize_manual_list_text(value: str | None) -> str:
    if not value:
        return ''
    text = str(value).replace(',', ';')
    text = re.sub(r'[\r\n\t]+', ';', text)
    return normalize_semicolon_text(text)


def split_styles(value: str | None) -> list[str]:
    return split_semicolon_values(value)


def split_raw_genres(value: str | None) -> list[str]:
    return split_semicolon_values(value)


def normalize_term_key(value: str) -> str:
    value = value.casefold().strip()
    value = value.replace('&', ' and ')
    value = re.sub(r'[/_,]+', ' ', value)
    value = re.sub(r'[^a-z0-9]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def add_genre(con: sqlite3.Connection, name: str) -> None:
    name = sanitize_value(name)
    con.execute('INSERT OR IGNORE INTO canonical_genre(name) VALUES (?)', (name,))
    con.commit()
    print(f'Genre ensured: {name}')


def add_style(con: sqlite3.Connection, genre: str, style: str) -> None:
    genre = sanitize_value(genre)
    style = sanitize_value(style)
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
    source = sanitize_value(source)
    raw = sanitize_value(raw)
    genre = sanitize_value(genre) if genre else None
    style = sanitize_value(style) if style else None
    notes = sanitize_value(notes) if notes else None
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


def map_raw_genre(
    con: sqlite3.Connection,
    raw: str,
    genre: str,
    style: str | None,
    source: str,
    notes: str | None,
    confidence: float,
    ensure_style: bool,
) -> None:
    raw = sanitize_value(raw)
    genre = sanitize_value(genre)
    style = sanitize_value(style) if style else None
    if style and ensure_style:
        add_style(con, genre, style)
    add_alias(con, source, raw, genre, style, notes, confidence)


def map_raw_style(
    con: sqlite3.Connection,
    raw: str,
    genre: str,
    style: str,
    notes: str | None,
    confidence: float,
    ensure_style: bool,
) -> None:
    raw = sanitize_value(raw)
    genre = sanitize_value(genre)
    style = sanitize_value(style)
    notes = sanitize_value(notes) if notes else None
    if ensure_style:
        add_style(con, genre, style)
    style_id = get_style_id(con, style)
    con.execute(
        '''
        INSERT INTO style_alias_mapping(raw_value, normalized_style_id, notes, confidence)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(raw_value) DO UPDATE SET
            normalized_style_id=excluded.normalized_style_id,
            notes=excluded.notes,
            confidence=excluded.confidence
        ''',
        (raw, style_id, notes, confidence),
    )
    con.commit()
    print(f'Style alias mapped: {raw} -> {style}')


def save_entity_decision(
    con: sqlite3.Connection,
    table: str,
    id_column: str,
    mbid: str,
    genre: str,
    styles: str,
    notes: str | None,
    locked: bool,
    ensure_styles: bool,
) -> None:
    mbid = sanitize_value(mbid)
    genre = normalize_manual_list_text(genre)
    styles = normalize_manual_list_text(styles)
    notes = sanitize_value(notes) if notes else None
    genre_id, primary_genre, genres_text = normalize_genres(con, genre)
    for style in split_styles(styles):
        if ensure_styles:
            add_style(con, primary_genre, style)
        else:
            get_style_id(con, style)
    con.execute(
        f'''
        INSERT INTO {table}(
            {id_column}, normalized_genre_id, genres_text, styles_text, notes, locked
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT({id_column}) DO UPDATE SET
            normalized_genre_id=excluded.normalized_genre_id,
            genres_text=excluded.genres_text,
            styles_text=excluded.styles_text,
            notes=excluded.notes,
            locked=excluded.locked,
            updated_at=CURRENT_TIMESTAMP
        ''',
        (mbid, genre_id, genres_text, styles, notes, int(locked)),
    )
    con.commit()


def decide_artist(
    con: sqlite3.Connection,
    artist_mbid: str,
    genre: str,
    styles: str,
    notes: str | None,
    locked: bool,
    ensure_styles: bool,
) -> None:
    save_entity_decision(
        con,
        'artist_decision',
        'artist_mbid',
        artist_mbid,
        genre,
        styles,
        notes,
        locked,
        ensure_styles,
    )
    print(f'Artist decision saved: {artist_mbid}')


def decide_release(
    con: sqlite3.Connection,
    release_mbid: str,
    genre: str,
    styles: str,
    notes: str | None,
    locked: bool,
    ensure_styles: bool,
) -> None:
    save_entity_decision(
        con,
        'release_decision',
        'release_mbid',
        release_mbid,
        genre,
        styles,
        notes,
        locked,
        ensure_styles,
    )
    print(f'Release decision saved: {release_mbid}')


def decide_release_group(
    con: sqlite3.Connection,
    release_group_mbid: str,
    genre: str,
    styles: str,
    notes: str | None,
    locked: bool,
    ensure_styles: bool,
) -> None:
    save_entity_decision(
        con,
        'release_group_decision',
        'release_group_mbid',
        release_group_mbid,
        genre,
        styles,
        notes,
        locked,
        ensure_styles,
    )
    print(f'Release-group decision saved: {release_group_mbid}')


def decide_recording(
    con: sqlite3.Connection,
    recording_mbid: str,
    genre: str,
    styles: str,
    notes: str | None,
    locked: bool,
    ensure_styles: bool,
) -> None:
    save_entity_decision(
        con,
        'recording_decision',
        'recording_mbid',
        recording_mbid,
        genre,
        styles,
        notes,
        locked,
        ensure_styles,
    )
    print(f'Recording decision saved: {recording_mbid}')


def list_table(con: sqlite3.Connection, sql: str, params: Iterable[object] = ()) -> None:
    rows = con.execute(sql, tuple(params)).fetchall()
    if not rows:
        print('No rows.')
        return
    for row in rows:
        print(dict(row))


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass


def import_library_csv(con: sqlite3.Connection, csv_path: str, source: str, replace: bool) -> None:
    path = Path(csv_path)
    if not path.exists():
        raise SystemExit(f'CSV not found: {path}')
    if replace:
        con.execute('DELETE FROM library_tag_import WHERE import_source = ?', (source,))

    columns = [
        'path',
        'title',
        'artist',
        'album',
        'albumartist',
        'date',
        'genre',
        'style',
        'grouping',
        'contentgroup',
        'musicbrainz_artistid',
        'musicbrainz_albumartistid',
        'musicbrainz_releaseartistid',
        'musicbrainz_albumid',
        'musicbrainz_releasegroupid',
        'musicbrainz_recordingid',
        'musicbrainz_trackid',
    ]
    inserted = 0
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            values = {column: (row.get(column) or '').strip() for column in columns}
            con.execute(
                '''
                INSERT INTO library_tag_import(
                    import_source, file_path, title, artist, album, albumartist, date,
                    raw_genre, raw_style, raw_grouping, raw_contentgroup,
                    musicbrainz_artistid, musicbrainz_albumartistid, musicbrainz_releaseartistid,
                    musicbrainz_albumid, musicbrainz_releasegroupid, musicbrainz_recordingid,
                    musicbrainz_trackid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(import_source, file_path) DO UPDATE SET
                    title=excluded.title,
                    artist=excluded.artist,
                    album=excluded.album,
                    albumartist=excluded.albumartist,
                    date=excluded.date,
                    raw_genre=excluded.raw_genre,
                    raw_style=excluded.raw_style,
                    raw_grouping=excluded.raw_grouping,
                    raw_contentgroup=excluded.raw_contentgroup,
                    musicbrainz_artistid=excluded.musicbrainz_artistid,
                    musicbrainz_albumartistid=excluded.musicbrainz_albumartistid,
                    musicbrainz_releaseartistid=excluded.musicbrainz_releaseartistid,
                    musicbrainz_albumid=excluded.musicbrainz_albumid,
                    musicbrainz_releasegroupid=excluded.musicbrainz_releasegroupid,
                    musicbrainz_recordingid=excluded.musicbrainz_recordingid,
                    musicbrainz_trackid=excluded.musicbrainz_trackid,
                    imported_at=CURRENT_TIMESTAMP
                ''',
                (
                    source,
                    values['path'],
                    values['title'],
                    values['artist'],
                    values['album'],
                    values['albumartist'],
                    values['date'],
                    values['genre'],
                    values['style'],
                    values['grouping'],
                    values['contentgroup'],
                    values['musicbrainz_artistid'],
                    values['musicbrainz_albumartistid'],
                    values['musicbrainz_releaseartistid'],
                    values['musicbrainz_albumid'],
                    values['musicbrainz_releasegroupid'],
                    values['musicbrainz_recordingid'],
                    values['musicbrainz_trackid'],
                ),
            )
            inserted += 1
    con.commit()
    print(f'Imported {inserted} rows from {path} as source {source!r}')


def list_import_summary(con: sqlite3.Connection, source: str, limit: int) -> None:
    row = con.execute(
        '''
        SELECT COUNT(*) AS tracks,
               SUM(CASE WHEN raw_genre != '' THEN 1 ELSE 0 END) AS with_genre,
               SUM(CASE WHEN raw_style != '' THEN 1 ELSE 0 END) AS with_style,
               SUM(CASE WHEN raw_grouping != '' THEN 1 ELSE 0 END) AS with_grouping,
               SUM(CASE WHEN musicbrainz_albumid != '' THEN 1 ELSE 0 END) AS with_album_mbid,
               SUM(CASE WHEN musicbrainz_albumartistid != '' THEN 1 ELSE 0 END) AS with_albumartist_mbid
        FROM library_tag_import
        WHERE import_source = ?
        ''',
        (source,),
    ).fetchone()
    print(dict(row))

    print('\nTop genre values:')
    list_table(
        con,
        '''
        SELECT raw_genre, COUNT(*) AS tracks
        FROM library_tag_import
        WHERE import_source = ? AND raw_genre != ''
        GROUP BY raw_genre
        ORDER BY tracks DESC, raw_genre
        LIMIT ?
        ''',
        (source, limit),
    )

    print('\nTop grouping/style values:')
    list_import_styles(con, source, limit)

    print('\nAlbum candidates with MusicBrainz IDs:')
    list_table(
        con,
        '''
        SELECT musicbrainz_albumid AS album_mbid,
               albumartist,
               album,
               raw_genre,
               COALESCE(NULLIF(raw_style, ''), raw_grouping) AS raw_style_or_grouping,
               COUNT(*) AS tracks
        FROM library_tag_import
        WHERE import_source = ?
          AND musicbrainz_albumid != ''
          AND (raw_genre != '' OR COALESCE(NULLIF(raw_style, ''), raw_grouping) != '')
        GROUP BY musicbrainz_albumid, albumartist, album, raw_genre, raw_style_or_grouping
        ORDER BY tracks DESC, albumartist, album
        LIMIT ?
        ''',
        (source, limit),
    )


def list_import_genres(con: sqlite3.Connection, source: str, only_invalid: bool, limit: int) -> None:
    allowed = {
        str(row['name']).casefold(): str(row['name'])
        for row in con.execute('SELECT name FROM canonical_genre')
    }
    aliases = {
        str(row['raw_value']).casefold(): {
            'mapped_genre': str(row['genre'] or ''),
            'mapped_style': str(row['style'] or ''),
        }
        for row in con.execute(
            '''
            SELECT am.raw_value, cg.name AS genre, cs.name AS style
            FROM alias_mapping am
            LEFT JOIN canonical_genre cg ON cg.id = am.normalized_genre_id
            LEFT JOIN canonical_style cs ON cs.id = am.normalized_style_id
            '''
        )
    }
    counts: dict[str, int] = {}
    for row in con.execute(
        '''
        SELECT raw_genre
        FROM library_tag_import
        WHERE import_source = ? AND raw_genre != ''
        ''',
        (source,),
    ):
        for genre in split_raw_genres(row['raw_genre']):
            counts[genre] = counts.get(genre, 0) + 1

    rows = []
    for raw_genre, tracks in counts.items():
        allowed_name = allowed.get(raw_genre.casefold(), '')
        alias = aliases.get(raw_genre.casefold(), {})
        mapped_genre = alias.get('mapped_genre', '')
        mapped_style = alias.get('mapped_style', '')
        if only_invalid and (allowed_name or mapped_genre or mapped_style):
            continue
        rows.append(
            {
                'raw_genre': raw_genre,
                'tracks': tracks,
                'allowed': bool(allowed_name),
                'canonical': allowed_name,
                'mapped_genre': mapped_genre,
                'mapped_style': mapped_style,
            }
        )

    rows.sort(key=lambda row: (-int(row['tracks']), str(row['raw_genre']).casefold()))
    if limit > 0:
        rows = rows[:limit]
    if not rows:
        print('No rows.')
        return
    for row in rows:
        print(row)


def list_import_styles(con: sqlite3.Connection, source: str, limit: int) -> None:
    counts = import_style_counts(con, source)
    style_aliases = {
        str(row['raw_value']).casefold(): str(row['style'])
        for row in con.execute(
            '''
            SELECT sam.raw_value, cs.name AS style
            FROM style_alias_mapping sam
            JOIN canonical_style cs ON cs.id = sam.normalized_style_id
            '''
        )
    }
    rows = [{'raw_style_or_grouping': value, 'tracks': tracks} for value, tracks in counts.items()]
    rows.sort(key=lambda row: (-int(row['tracks']), str(row['raw_style_or_grouping']).casefold()))
    if limit > 0:
        rows = rows[:limit]
    if not rows:
        print('No rows.')
        return
    for row in rows:
        mapped = style_aliases.get(str(row['raw_style_or_grouping']).casefold())
        if mapped:
            row['mapped_style'] = mapped
        print(row)


def import_style_counts(con: sqlite3.Connection, source: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in con.execute(
        '''
        SELECT raw_style, raw_grouping
        FROM library_tag_import
        WHERE import_source = ?
          AND COALESCE(NULLIF(raw_style, ''), raw_grouping) != ''
        ''',
        (source,),
    ):
        raw_value = row['raw_style'] or row['raw_grouping']
        for style in split_semicolon_values(raw_value):
            counts[style] = counts.get(style, 0) + 1
    return counts


def contentgroup_report(con: sqlite3.Connection, source: str, limit: int) -> None:
    rows = []
    for row in con.execute(
        '''
        SELECT file_path, artist, album, title, raw_grouping, raw_contentgroup
        FROM library_tag_import
        WHERE import_source = ?
          AND COALESCE(raw_contentgroup, '') != ''
        ORDER BY albumartist, album, title, file_path
        ''',
        (source,),
    ):
        grouping = normalize_semicolon_text(row['raw_grouping'])
        contentgroup = normalize_semicolon_text(row['raw_contentgroup'])
        if grouping and contentgroup and grouping == contentgroup:
            status = 'duplicate'
        elif grouping and contentgroup:
            status = 'conflict'
        else:
            status = 'contentgroup_only'
        rows.append({
            'status': status,
            'artist': row['artist'],
            'album': row['album'],
            'title': row['title'],
            'grouping': grouping,
            'contentgroup': contentgroup,
            'path': row['file_path'],
        })
    if not rows:
        print('No contentgroup rows.')
        return
    counts: dict[str, int] = {}
    for row in rows:
        counts[row['status']] = counts.get(row['status'], 0) + 1
    print('Contentgroup summary:')
    for status in ('contentgroup_only', 'duplicate', 'conflict'):
        print(f'  {status}: {counts.get(status, 0)}')
    print('\nRows:')
    for row in rows[:limit]:
        print(row)


def target_mbid_for_scope(row: sqlite3.Row, scope: str) -> str:
    if scope == 'artist':
        for key in ('musicbrainz_albumartistid', 'musicbrainz_releaseartistid', 'musicbrainz_artistid'):
            value = single_mbid_value(row[key])
            if value:
                return value
        return ''
    if scope in ('release', 'album'):
        return str(row['musicbrainz_albumid'] or '').strip()
    if scope == 'release_group':
        return str(row['musicbrainz_releasegroupid'] or '').strip()
    if scope in ('recording', 'track'):
        return str(row['musicbrainz_recordingid'] or '').strip()
    raise SystemExit(f'Unknown scope: {scope}')


def single_mbid_value(value: str | None) -> str:
    value = (value or '').strip()
    if not value:
        return ''
    if ';' in value or '/' in value:
        return ''
    return value


def promote_imported_decisions(
    con: sqlite3.Connection,
    source: str,
    scope: str,
    apply: bool,
    plugin_json_path: str,
    limit: int,
) -> None:
    rows = con.execute(
        '''
        SELECT
            title,
            artist,
            album,
            albumartist,
            raw_genre,
            raw_style,
            raw_grouping,
            musicbrainz_artistid,
            musicbrainz_albumartistid,
            musicbrainz_releaseartistid,
            musicbrainz_albumid,
            musicbrainz_releasegroupid,
            musicbrainz_recordingid
        FROM library_tag_import
        WHERE import_source = ?
          AND raw_genre != ''
          AND COALESCE(NULLIF(raw_grouping, ''), raw_style) != ''
        ''',
        (source,),
    ).fetchall()

    candidates: dict[tuple[str, str, str], dict] = {}
    skipped_missing_mbid = 0
    for row in rows:
        mbid = target_mbid_for_scope(row, scope)
        if not mbid:
            skipped_missing_mbid += 1
            continue
        genre = '; '.join(split_semicolon_values(row['raw_genre']))
        styles = '; '.join(split_semicolon_values(row['raw_grouping'] or row['raw_style']))
        if not genre or not styles:
            continue
        key = (mbid, genre, styles)
        candidate = candidates.setdefault(
            key,
            {
                'scope': scope,
                'mbid': mbid,
                'genre': genre,
                'styles': styles,
                'tracks': 0,
                'albumartist': row['albumartist'] or '',
                'artist': row['artist'] or '',
                'album': row['album'] or '',
            },
        )
        candidate['tracks'] += 1

    sorted_candidates = sorted(
        candidates.values(),
        key=lambda item: (-int(item['tracks']), str(item['albumartist']).casefold(), str(item['album']).casefold()),
    )
    if limit > 0:
        sorted_candidates = sorted_candidates[:limit]
    if not sorted_candidates:
        print('No decision candidates.')
        if skipped_missing_mbid:
            print(f'Skipped rows missing a {scope} MBID: {skipped_missing_mbid}')
        return

    imported = 0
    for candidate in sorted_candidates:
        print(candidate)
        if not apply:
            continue
        if scope == 'artist':
            decide_artist(con, candidate['mbid'], candidate['genre'], candidate['styles'], None, False, True)
        elif scope in ('release', 'album'):
            decide_release(con, candidate['mbid'], candidate['genre'], candidate['styles'], None, False, True)
        elif scope == 'release_group':
            decide_release_group(con, candidate['mbid'], candidate['genre'], candidate['styles'], None, False, True)
        elif scope in ('recording', 'track'):
            decide_recording(con, candidate['mbid'], candidate['genre'], candidate['styles'], None, False, True)
        imported += 1

    if apply:
        export_plugin_json(con, plugin_json_path)
        print(f'Imported {imported} decisions from source {source!r}.')
    else:
        print('Preview only. Re-run with --apply to import these decisions.')
    if skipped_missing_mbid:
        print(f'Skipped rows missing a {scope} MBID: {skipped_missing_mbid}')


def list_import_style_clusters(con: sqlite3.Connection, source: str, limit: int) -> None:
    counts = import_style_counts(con, source)
    clusters: dict[str, dict] = {}
    for value, tracks in counts.items():
        key = normalize_term_key(value)
        if not key:
            continue
        cluster = clusters.setdefault(key, {'normalized_key': key, 'tracks': 0, 'values': []})
        cluster['tracks'] += tracks
        cluster['values'].append((value, tracks))

    rows = []
    for cluster in clusters.values():
        values = sorted(cluster['values'], key=lambda item: (-item[1], item[0].casefold()))
        unique_values = [f'{value} ({tracks})' for value, tracks in values]
        rows.append(
            {
                'normalized_key': cluster['normalized_key'],
                'tracks': cluster['tracks'],
                'variants': len(values),
                'values': '; '.join(unique_values[:8]),
            }
        )
    rows.sort(key=lambda row: (-int(row['variants']), -int(row['tracks']), str(row['normalized_key'])))
    if limit > 0:
        rows = rows[:limit]
    if not rows:
        print('No rows.')
        return
    for row in rows:
        print(row)


def list_plugin_runs(con: sqlite3.Connection, limit: int) -> None:
    list_table(
        con,
        '''
        SELECT id, seen_at, entity_type, title, artist, album,
               recording_mbid, release_mbid, release_group_mbid,
               album_artist_mbids, track_artist_mbids,
               decision_source, decision_mbid, applied_genre, applied_styles,
               wrote_genre, wrote_style, wrote_contentgroup, wrote_grouping
        FROM plugin_run_log
        ORDER BY id DESC
        LIMIT ?
        ''',
        (limit,),
    )


def clear_plugin_runs(con: sqlite3.Connection) -> None:
    con.execute('DELETE FROM plugin_run_log')
    con.commit()
    print('Plugin run log cleared.')


def clean_decision_text(con: sqlite3.Connection) -> None:
    changed = 0
    for table, id_column in (
        ('artist_decision', 'artist_mbid'),
        ('release_decision', 'release_mbid'),
        ('release_group_decision', 'release_group_mbid'),
        ('recording_decision', 'recording_mbid'),
    ):
        rows = con.execute(
            f'SELECT {id_column} AS mbid, genres_text, styles_text, notes FROM {table}'
        ).fetchall()
        for row in rows:
            genres_text = normalize_semicolon_text(row['genres_text'])
            styles_text = normalize_semicolon_text(row['styles_text'])
            notes = sanitize_value(row['notes']) if row['notes'] else None
            if (
                genres_text != (row['genres_text'] or '')
                or styles_text != (row['styles_text'] or '')
                or notes != row['notes']
            ):
                con.execute(
                    f'''
                    UPDATE {table}
                    SET genres_text = ?, styles_text = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE {id_column} = ?
                    ''',
                    (genres_text, styles_text, notes, row['mbid']),
                )
                changed += 1
    con.commit()
    print(f'Cleaned {changed} decision rows.')


def export_plugin_json(con: sqlite3.Connection, output_path: str) -> None:
    def decision_rows(table: str, id_column: str) -> dict[str, dict[str, str]]:
        rows = con.execute(
            f'''
            SELECT
                d.{id_column} AS mbid,
                COALESCE(NULLIF(d.genres_text, ''), cg.name) AS genre,
                d.styles_text AS styles
            FROM {table} d
            JOIN canonical_genre cg ON cg.id = d.normalized_genre_id
            '''
        ).fetchall()
        return {
            str(row['mbid']): {
                'genre': str(row['genre'] or ''),
                'styles': str(row['styles'] or ''),
            }
            for row in rows
        }

    alias_rows = con.execute(
        '''
        SELECT am.raw_value, cg.name AS genre, cs.name AS style
        FROM alias_mapping am
        LEFT JOIN canonical_genre cg ON cg.id = am.normalized_genre_id
        LEFT JOIN canonical_style cs ON cs.id = am.normalized_style_id
        ORDER BY am.confidence DESC, am.id ASC
        '''
    ).fetchall()
    aliases = {}
    for row in alias_rows:
        key = str(row['raw_value'] or '').casefold()
        if key and key not in aliases:
            aliases[key] = {
                'genre': str(row['genre'] or ''),
                'style': str(row['style'] or ''),
            }

    data = {
        'artist_decisions': decision_rows('artist_decision', 'artist_mbid'),
        'release_decisions': decision_rows('release_decision', 'release_mbid'),
        'release_group_decisions': decision_rows('release_group_decision', 'release_group_mbid'),
        'recording_decisions': decision_rows('recording_decision', 'recording_mbid'),
        'aliases': aliases,
    }

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
    print(f'Exported plugin snapshot to {path}')


def load_pending_rows(pending_path: str) -> list[dict]:
    path = Path(pending_path)
    if not path.exists():
        return []
    rows = []
    with path.open(encoding='utf-8-sig') as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f'Invalid JSON on {path}:{line_number}: {exc}')
    return rows


def list_pending_decisions(pending_path: str) -> None:
    rows = load_pending_rows(pending_path)
    if not rows:
        print('No rows.')
        return
    seen = set()
    for row in rows:
        key = (row.get('scope'), row.get('mbid'), row.get('genre'), row.get('styles'))
        if key in seen:
            continue
        seen.add(key)
        print(
            {
                'scope': row.get('scope', ''),
                'mbid': row.get('mbid', ''),
                'genre': row.get('genre', ''),
                'styles': row.get('styles', ''),
                'artist': row.get('artist', ''),
                'album': row.get('album', ''),
                'title': row.get('title', ''),
            }
        )


def import_pending_decisions(
    con: sqlite3.Connection,
    pending_path: str,
    plugin_json_path: str,
    clear: bool,
) -> None:
    rows = load_pending_rows(pending_path)
    if not rows:
        print('No pending decisions.')
        return
    imported = 0
    seen = set()
    for row in rows:
        scope = str(row.get('scope') or '')
        mbid = str(row.get('mbid') or '')
        genre = str(row.get('genre') or '')
        styles = str(row.get('styles') or '')
        if not scope or not mbid or not genre:
            continue
        key = (scope, mbid, genre, styles)
        if key in seen:
            continue
        seen.add(key)
        if scope == 'artist':
            decide_artist(con, mbid, genre, styles, None, False, True)
        elif scope == 'release':
            decide_release(con, mbid, genre, styles, None, False, True)
        elif scope == 'release_group':
            decide_release_group(con, mbid, genre, styles, None, False, True)
        elif scope == 'recording':
            decide_recording(con, mbid, genre, styles, None, False, True)
        else:
            continue
        imported += 1
    export_plugin_json(con, plugin_json_path)
    if clear:
        Path(pending_path).unlink(missing_ok=True)
        print(f'Cleared {pending_path}')
    print(f'Imported {imported} pending decisions.')


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

    p = sub.add_parser('map-raw-genre')
    p.add_argument('--raw', required=True)
    p.add_argument('--genre', required=True)
    p.add_argument('--style')
    p.add_argument('--source', default='library')
    p.add_argument('--notes')
    p.add_argument('--confidence', type=float, default=1.0)
    p.add_argument('--ensure-style', action=argparse.BooleanOptionalAction, default=True)

    p = sub.add_parser('map-raw-style')
    p.add_argument('--raw', required=True)
    p.add_argument('--genre', required=True)
    p.add_argument('--style', required=True)
    p.add_argument('--notes')
    p.add_argument('--confidence', type=float, default=1.0)
    p.add_argument('--ensure-style', action=argparse.BooleanOptionalAction, default=True)

    p = sub.add_parser('import-library-csv')
    p.add_argument('csv_path')
    p.add_argument('--source', default='library_export')
    p.add_argument('--replace', action='store_true')

    p = sub.add_parser('list-import-summary')
    p.add_argument('--source', default='library_export')
    p.add_argument('--limit', type=int, default=25)

    p = sub.add_parser('list-import-genres')
    p.add_argument('--source', default='library_export')
    p.add_argument('--only-invalid', action='store_true')
    p.add_argument('--limit', type=int, default=100)

    p = sub.add_parser('list-import-styles')
    p.add_argument('--source', default='library_export')
    p.add_argument('--limit', type=int, default=100)

    p = sub.add_parser('list-import-style-clusters')
    p.add_argument('--source', default='library_export')
    p.add_argument('--limit', type=int, default=100)

    p = sub.add_parser('list-import-contentgroups')
    p.add_argument('--source', default='library_export')
    p.add_argument('--limit', type=int, default=100)

    p = sub.add_parser('promote-imported-decisions')
    p.add_argument('--source', default='library_export')
    p.add_argument(
        '--scope',
        choices=('artist', 'release', 'album', 'release_group', 'recording', 'track'),
        default='artist',
    )
    p.add_argument('--apply', action='store_true')
    p.add_argument('--plugin-json', default='taxonomy.json')
    p.add_argument('--limit', type=int, default=25)

    p = sub.add_parser('list-plugin-runs')
    p.add_argument('--limit', type=int, default=25)

    sub.add_parser('clear-plugin-runs')

    sub.add_parser('clean-decision-text')

    p = sub.add_parser('export-plugin-json')
    p.add_argument('--out', default='taxonomy.json')

    p = sub.add_parser('list-pending-decisions')
    p.add_argument('--pending', default='local_genre_db_pending.jsonl')

    p = sub.add_parser('import-pending-decisions')
    p.add_argument('--pending', default='local_genre_db_pending.jsonl')
    p.add_argument('--plugin-json', default='taxonomy.json')
    p.add_argument('--clear', action=argparse.BooleanOptionalAction, default=True)

    p = sub.add_parser('decide-artist')
    p.add_argument('--artist-mbid', required=True)
    p.add_argument('--genre', required=True)
    p.add_argument('--styles', default='')
    p.add_argument('--notes')
    p.add_argument('--locked', action='store_true', default=False)
    p.add_argument('--ensure-styles', action=argparse.BooleanOptionalAction, default=True)

    p = sub.add_parser('decide-release')
    p.add_argument('--release-mbid', required=True)
    p.add_argument('--genre', required=True)
    p.add_argument('--styles', default='')
    p.add_argument('--notes')
    p.add_argument('--locked', action='store_true', default=False)
    p.add_argument('--ensure-styles', action=argparse.BooleanOptionalAction, default=True)

    p = sub.add_parser('decide-album')
    p.add_argument('--album-mbid', '--release-mbid', dest='release_mbid', required=True)
    p.add_argument('--genre', required=True)
    p.add_argument('--styles', default='')
    p.add_argument('--notes')
    p.add_argument('--locked', action='store_true', default=False)
    p.add_argument('--ensure-styles', action=argparse.BooleanOptionalAction, default=True)

    p = sub.add_parser('decide-release-group')
    p.add_argument('--release-group-mbid', required=True)
    p.add_argument('--genre', required=True)
    p.add_argument('--styles', default='')
    p.add_argument('--notes')
    p.add_argument('--locked', action='store_true', default=False)
    p.add_argument('--ensure-styles', action=argparse.BooleanOptionalAction, default=True)

    p = sub.add_parser('decide-recording')
    p.add_argument('--recording-mbid', required=True)
    p.add_argument('--genre', required=True)
    p.add_argument('--styles', default='')
    p.add_argument('--notes')
    p.add_argument('--locked', action='store_true', default=False)
    p.add_argument('--ensure-styles', action=argparse.BooleanOptionalAction, default=True)

    sub.add_parser('list-genres')
    sub.add_parser('list-styles')
    sub.add_parser('list-aliases')
    sub.add_parser('list-artist-decisions')
    sub.add_parser('list-album-decisions')
    sub.add_parser('list-release-decisions')
    sub.add_parser('list-release-group-decisions')
    sub.add_parser('list-recording-decisions')

    return parser


def main() -> int:
    configure_output()
    parser = build_parser()
    args = parser.parse_args()
    con = connect(args.db)
    try:
        ensure_schema(con)
        if args.command == 'add-genre':
            add_genre(con, args.name)
        elif args.command == 'add-style':
            add_style(con, args.genre, args.style)
        elif args.command == 'add-alias':
            add_alias(con, args.source, args.raw, args.genre, args.style, args.notes, args.confidence)
        elif args.command == 'map-raw-genre':
            map_raw_genre(
                con,
                args.raw,
                args.genre,
                args.style,
                args.source,
                args.notes,
                args.confidence,
                args.ensure_style,
            )
        elif args.command == 'map-raw-style':
            map_raw_style(
                con,
                args.raw,
                args.genre,
                args.style,
                args.notes,
                args.confidence,
                args.ensure_style,
            )
        elif args.command == 'import-library-csv':
            import_library_csv(con, args.csv_path, args.source, args.replace)
        elif args.command == 'list-import-summary':
            list_import_summary(con, args.source, args.limit)
        elif args.command == 'list-import-genres':
            list_import_genres(con, args.source, args.only_invalid, args.limit)
        elif args.command == 'list-import-styles':
            list_import_styles(con, args.source, args.limit)
        elif args.command == 'list-import-style-clusters':
            list_import_style_clusters(con, args.source, args.limit)
        elif args.command == 'list-import-contentgroups':
            contentgroup_report(con, args.source, args.limit)
        elif args.command == 'promote-imported-decisions':
            promote_imported_decisions(
                con,
                args.source,
                args.scope,
                args.apply,
                args.plugin_json,
                args.limit,
            )
        elif args.command == 'list-plugin-runs':
            list_plugin_runs(con, args.limit)
        elif args.command == 'clear-plugin-runs':
            clear_plugin_runs(con)
        elif args.command == 'clean-decision-text':
            clean_decision_text(con)
            export_plugin_json(con, 'taxonomy.json')
        elif args.command == 'export-plugin-json':
            export_plugin_json(con, args.out)
        elif args.command == 'list-pending-decisions':
            list_pending_decisions(args.pending)
        elif args.command == 'import-pending-decisions':
            import_pending_decisions(con, args.pending, args.plugin_json, args.clear)
        elif args.command == 'decide-artist':
            decide_artist(
                con,
                args.artist_mbid,
                args.genre,
                args.styles,
                args.notes,
                args.locked,
                args.ensure_styles,
            )
        elif args.command in ('decide-release', 'decide-album'):
            decide_release(
                con,
                args.release_mbid,
                args.genre,
                args.styles,
                args.notes,
                args.locked,
                args.ensure_styles,
            )
        elif args.command == 'decide-release-group':
            decide_release_group(
                con,
                args.release_group_mbid,
                args.genre,
                args.styles,
                args.notes,
                args.locked,
                args.ensure_styles,
            )
        elif args.command == 'decide-recording':
            decide_recording(
                con,
                args.recording_mbid,
                args.genre,
                args.styles,
                args.notes,
                args.locked,
                args.ensure_styles,
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
        elif args.command == 'list-artist-decisions':
            list_table(con, 'SELECT * FROM artist_decision ORDER BY updated_at DESC')
        elif args.command in ('list-release-decisions', 'list-album-decisions'):
            list_table(con, 'SELECT * FROM release_decision ORDER BY updated_at DESC')
        elif args.command == 'list-release-group-decisions':
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
