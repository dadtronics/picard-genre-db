# -*- coding: utf-8 -*-
"""
Local Genre DB

Picard plugin that applies normalized genre/style values from a local SQLite DB.

Resolution order:
1. recording_decision by musicbrainz_recordingid
2. release_group_decision by musicbrainz_releasegroupid
3. alias_mapping using any raw genre/style value already present in metadata

Notes:
- This starter keeps configuration intentionally simple.
- Set TAXONOMY_DB_PATH below to your SQLite database path.
- Set OVERWRITE_EXISTING to True if you want this plugin to replace existing values.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Iterable, List, Optional, Set

from picard import log
from picard.metadata import register_album_metadata_processor, register_track_metadata_processor

PLUGIN_NAME = 'Local Genre DB'
PLUGIN_AUTHOR = 'OpenAI'
PLUGIN_DESCRIPTION = 'Apply canonical genre/style tags from a local SQLite taxonomy database.'
PLUGIN_VERSION = '0.1.0'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2']
PLUGIN_LICENSE = 'MIT'
PLUGIN_LICENSE_URL = 'https://opensource.org/licenses/MIT'

# Adjust this path for your system, or define PICARD_TAXONOMY_DB in your environment.
TAXONOMY_DB_PATH = os.environ.get('PICARD_TAXONOMY_DB', os.path.expanduser('~/taxonomy.db'))
OVERWRITE_EXISTING = False
WRITE_STYLE_TAG = True
LOG_RAW_VALUES = True


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(TAXONOMY_DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _get_tag(metadata, name: str, default: str = '') -> str:
    try:
        value = metadata.get(name, default)
    except Exception:
        try:
            value = metadata[name]
        except Exception:
            return default
    if value is None:
        return default
    if isinstance(value, list):
        return '; '.join(str(v) for v in value if v)
    return str(value)


def _set_tag(metadata, name: str, value: str) -> None:
    metadata[name] = value


def _is_blank(value: str) -> bool:
    return not value or not value.strip()


def _should_write(metadata, tag_name: str) -> bool:
    current = _get_tag(metadata, tag_name, '')
    return OVERWRITE_EXISTING or _is_blank(current)


def _split_values(value: str) -> List[str]:
    if not value:
        return []
    normalized = value.replace('/', ';')
    parts = [part.strip() for part in normalized.split(';')]
    return [part for part in parts if part]


def _collect_raw_terms(metadata) -> List[str]:
    terms: List[str] = []
    for tag_name in ('genre', 'style'):
        raw = _get_tag(metadata, tag_name, '')
        terms.extend(_split_values(raw))
    seen: Set[str] = set()
    ordered: List[str] = []
    for term in terms:
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            ordered.append(term)
    return ordered


def _log_raw_values(con: sqlite3.Connection, entity_type: str, entity_mbid: str, values: Iterable[str], value_type: str) -> None:
    for raw in values:
        con.execute(
            '''
            INSERT INTO raw_value_log(source_name, entity_type, entity_mbid, raw_value, value_type)
            VALUES (?, ?, ?, ?, ?)
            ''',
            ('picard_existing', entity_type, entity_mbid, raw, value_type),
        )


def _lookup_decision(con: sqlite3.Connection, recording_mbid: str, release_group_mbid: str):
    if recording_mbid:
        row = con.execute(
            '''
            SELECT cg.name AS genre, rd.styles_text AS styles
            FROM recording_decision rd
            JOIN canonical_genre cg ON cg.id = rd.normalized_genre_id
            WHERE rd.recording_mbid = ?
            ''',
            (recording_mbid,),
        ).fetchone()
        if row:
            return dict(row)

    if release_group_mbid:
        row = con.execute(
            '''
            SELECT cg.name AS genre, rgd.styles_text AS styles
            FROM release_group_decision rgd
            JOIN canonical_genre cg ON cg.id = rgd.normalized_genre_id
            WHERE rgd.release_group_mbid = ?
            ''',
            (release_group_mbid,),
        ).fetchone()
        if row:
            return dict(row)

    return None


def _lookup_aliases(con: sqlite3.Connection, raw_terms: Iterable[str]):
    genre_name: Optional[str] = None
    styles: List[str] = []
    seen_styles: Set[str] = set()

    for raw in raw_terms:
        row = con.execute(
            '''
            SELECT cg.name AS genre, cs.name AS style
            FROM alias_mapping am
            LEFT JOIN canonical_genre cg ON cg.id = am.normalized_genre_id
            LEFT JOIN canonical_style cs ON cs.id = am.normalized_style_id
            WHERE am.raw_value = ?
            ORDER BY am.confidence DESC, am.id ASC
            LIMIT 1
            ''',
            (raw,),
        ).fetchone()
        if not row:
            continue
        if row['genre'] and not genre_name:
            genre_name = str(row['genre'])
        if row['style']:
            style = str(row['style'])
            if style.casefold() not in seen_styles:
                seen_styles.add(style.casefold())
                styles.append(style)

    if not genre_name and not styles:
        return None

    return {
        'genre': genre_name or '',
        'styles': '; '.join(styles),
    }


def _apply_metadata(metadata, decision) -> None:
    genre = (decision.get('genre') or '').strip()
    styles = (decision.get('styles') or '').strip()

    if genre and _should_write(metadata, 'genre'):
        _set_tag(metadata, 'genre', genre)

    if WRITE_STYLE_TAG and styles and _should_write(metadata, 'style'):
        _set_tag(metadata, 'style', styles)


def _process_metadata(metadata, entity_type: str) -> None:
    if not os.path.exists(TAXONOMY_DB_PATH):
        log.warning('Local Genre DB: taxonomy DB not found at %r', TAXONOMY_DB_PATH)
        return

    release_group_mbid = _get_tag(metadata, 'musicbrainz_releasegroupid', '').strip()
    recording_mbid = _get_tag(metadata, 'musicbrainz_recordingid', '').strip()
    raw_terms = _collect_raw_terms(metadata)

    try:
        con = _connect()
    except Exception as exc:
        log.error('Local Genre DB: failed opening %r: %s', TAXONOMY_DB_PATH, exc)
        return

    try:
        if LOG_RAW_VALUES and raw_terms:
            _log_raw_values(con, entity_type, recording_mbid or release_group_mbid, raw_terms, 'genre_or_style')

        decision = _lookup_decision(con, recording_mbid, release_group_mbid)
        if not decision and raw_terms:
            decision = _lookup_aliases(con, raw_terms)

        if decision:
            _apply_metadata(metadata, decision)
            log.debug(
                'Local Genre DB: applied genre=%r style=%r for recording=%r releasegroup=%r',
                decision.get('genre'),
                decision.get('styles'),
                recording_mbid,
                release_group_mbid,
            )

        con.commit()
    except Exception as exc:
        log.error('Local Genre DB: processing failed: %s', exc)
    finally:
        con.close()


def process_album(tagger, metadata, release):
    _process_metadata(metadata, 'release')


def process_track(tagger, metadata, track, release):
    _process_metadata(metadata, 'recording')


register_album_metadata_processor(process_album)
register_track_metadata_processor(process_track)
