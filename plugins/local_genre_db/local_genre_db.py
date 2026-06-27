# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 rb303
PLUGIN_NAME = 'Local Genre DB'
PLUGIN_AUTHOR = 'rb303'
PLUGIN_DESCRIPTION = 'Apply canonical genre/style tags from a local taxonomy snapshot.'
PLUGIN_VERSION = '0.3.0'
PLUGIN_API_VERSIONS = [
    '2.0', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7',
    '2.8', '2.9', '2.10', '2.11', '2.12', '2.13',
]
PLUGIN_LICENSE = 'GPL-2.0-or-later'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/old-licenses/gpl-2.0.html'

import json
import os
from datetime import datetime
from typing import Iterable, List, Optional, Set

from picard import log
from picard.metadata import register_album_metadata_processor, register_track_metadata_processor

TAXONOMY_DB_PATH = os.path.expanduser('~/taxonomy.db')
TAXONOMY_JSON_PATH = os.path.expanduser('~/taxonomy.json')
PREFER_SQLITE = True
OVERWRITE_EXISTING = False
OVERWRITE_WITH_DECISIONS = True
WRITE_STYLE_TAG = False
WRITE_GROUPING_TAG = True
REMOVE_DUPLICATE_STYLE_TAG = True
LEARN_FROM_METADATA = True
LEARN_DEFAULT_SCOPE = 'artist'


def _plugin_dir() -> str:
    plugin_dir = os.path.dirname(__file__)
    zip_marker = '.zip'
    if zip_marker in plugin_dir.casefold():
        zip_index = plugin_dir.casefold().index(zip_marker) + len(zip_marker)
        plugin_dir = os.path.dirname(plugin_dir[:zip_index])
    return plugin_dir


def _append_file_log(message: str) -> None:
    try:
        log_path = os.path.join(_plugin_dir(), 'local_genre_db_load.log')
        with open(log_path, 'a', encoding='utf-8') as handle:
            handle.write(f'{datetime.now().isoformat(timespec="seconds")} {message}\n')
    except Exception:
        pass


def _taxonomy_json_path() -> str:
    env_path = os.environ.get('PICARD_TAXONOMY_JSON', '').strip()
    if env_path:
        return os.path.expanduser(env_path)

    config_path = os.path.join(_plugin_dir(), 'taxonomy_json_path.txt')
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as config_file:
            file_path = config_file.readline().strip().lstrip('\ufeff')
    except OSError:
        file_path = ''
    if file_path:
        return os.path.expanduser(file_path)

    return TAXONOMY_JSON_PATH


def _taxonomy_db_path() -> str:
    env_path = os.environ.get('PICARD_TAXONOMY_DB', '').strip()
    if env_path:
        return os.path.expanduser(env_path)

    config_path = os.path.join(_plugin_dir(), 'taxonomy_path.txt')
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as config_file:
            file_path = config_file.readline().strip().lstrip('\ufeff')
    except OSError:
        file_path = ''
    if file_path:
        return os.path.expanduser(file_path)

    return TAXONOMY_DB_PATH


def _pending_path() -> str:
    return os.path.join(_plugin_dir(), 'local_genre_db_pending.jsonl')


def _preferred_scope(metadata) -> str:
    value = _get_tag(metadata, 'local_genre_db_scope', '').strip().casefold()
    if value in ('artist', 'album', 'release', 'release_group', 'release-group', 'track', 'recording'):
        return value
    return LEARN_DEFAULT_SCOPE


def _pending_target(
    metadata,
    recording_mbid: str,
    release_mbid: str,
    release_group_mbid: str,
    album_artist_mbids: Iterable[str],
    track_artist_mbids: Iterable[str],
):
    scope = _preferred_scope(metadata)
    if scope == 'artist':
        mbids = list(album_artist_mbids) or list(track_artist_mbids)
        if mbids:
            return 'artist', mbids[0]
    if scope in ('album', 'release') and release_mbid:
        return 'release', release_mbid
    if scope in ('release_group', 'release-group') and release_group_mbid:
        return 'release_group', release_group_mbid
    if scope in ('track', 'recording') and recording_mbid:
        return 'recording', recording_mbid
    return '', ''


def _append_pending_decision(
    metadata,
    recording_mbid: str,
    release_mbid: str,
    release_group_mbid: str,
    album_artist_mbids: Iterable[str],
    track_artist_mbids: Iterable[str],
) -> None:
    if not LEARN_FROM_METADATA:
        return
    genre = _get_tag(metadata, 'genre', '').strip()
    styles = (
        _get_tag(metadata, 'grouping', '').strip() or
        _get_tag(metadata, 'contentgroup', '').strip() or
        _get_tag(metadata, 'style', '').strip()
    )
    if not genre or not styles:
        return
    scope, mbid = _pending_target(
        metadata,
        recording_mbid,
        release_mbid,
        release_group_mbid,
        album_artist_mbids,
        track_artist_mbids,
    )
    if not scope or not mbid:
        return
    row = {
        'scope': scope,
        'mbid': mbid,
        'genre': genre,
        'styles': styles,
        'title': _get_tag(metadata, 'title', ''),
        'artist': _get_tag(metadata, 'artist', ''),
        'album': _get_tag(metadata, 'album', ''),
        'recording_mbid': recording_mbid,
        'release_mbid': release_mbid,
        'release_group_mbid': release_group_mbid,
        'album_artist_mbids': list(album_artist_mbids),
        'track_artist_mbids': list(track_artist_mbids),
        'learned_at': datetime.now().isoformat(timespec='seconds'),
    }
    try:
        with open(_pending_path(), 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, sort_keys=True) + '\n')
        _append_file_log(f'pending scope={scope!r} mbid={mbid!r} genre={genre!r} styles={styles!r}')
    except Exception as exc:
        _append_file_log(f'pending_error={exc!r}')


def _load_snapshot():
    db_path = _taxonomy_db_path()
    if PREFER_SQLITE and db_path and os.path.exists(db_path):
        try:
            return _load_sqlite_snapshot(db_path)
        except ImportError as exc:
            _append_file_log(f'sqlite_unavailable={exc!r}')
        except Exception as exc:
            _append_file_log(f'sqlite_snapshot_error={exc!r}')

    json_path = _taxonomy_json_path()
    with open(json_path, 'r', encoding='utf-8-sig') as handle:
        return json.load(handle)


def _load_sqlite_snapshot(db_path: str):
    import sqlite3

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        def decision_rows(table: str, id_column: str):
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

        return {
            'artist_decisions': decision_rows('artist_decision', 'artist_mbid'),
            'release_decisions': decision_rows('release_decision', 'release_mbid'),
            'release_group_decisions': decision_rows('release_group_decision', 'release_group_mbid'),
            'recording_decisions': decision_rows('recording_decision', 'recording_mbid'),
            'aliases': aliases,
        }
    finally:
        con.close()


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
    values = _split_semicolon(value)
    metadata[name] = values if values else value


def _delete_tag(metadata, name: str) -> bool:
    try:
        if name in metadata:
            del metadata[name]
            return True
    except Exception:
        pass
    return False


def _should_write(metadata, tag_name: str, force: bool = False) -> bool:
    current = _get_tag(metadata, tag_name, '')
    return force or OVERWRITE_EXISTING or not current.strip()


def _same_semicolon_values(left: str, right: str) -> bool:
    return _split_semicolon(left) == _split_semicolon(right)


def _split_semicolon(value: str) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(';') if part.strip()]


def _split_ids(value: str) -> List[str]:
    if not value:
        return []
    normalized = value.replace(';', ',')
    return [part.strip() for part in normalized.split(',') if part.strip()]


def _collect_raw_terms(metadata) -> List[str]:
    terms: List[str] = []
    for tag_name in ('genre', 'style', 'contentgroup', 'grouping'):
        terms.extend(_split_semicolon(_get_tag(metadata, tag_name, '')))
    seen: Set[str] = set()
    ordered: List[str] = []
    for term in terms:
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            ordered.append(term)
    return ordered


def _lookup_artist_decision(snapshot, artist_mbids: Iterable[str]):
    artist_decisions = snapshot.get('artist_decisions', {})
    for artist_mbid in artist_mbids:
        decision = artist_decisions.get(artist_mbid)
        if decision:
            result = dict(decision)
            result['source'] = 'artist'
            result['source_mbid'] = artist_mbid
            return result
    return None


def _lookup_decision(
    snapshot,
    recording_mbid: str,
    release_mbid: str,
    release_group_mbid: str,
    album_artist_mbids: Iterable[str],
    track_artist_mbids: Iterable[str],
):
    lookups = (
        ('recording', 'recording_decisions', recording_mbid),
        ('release', 'release_decisions', release_mbid),
        ('release_group', 'release_group_decisions', release_group_mbid),
    )
    for source, key, mbid in lookups:
        if not mbid:
            continue
        decision = snapshot.get(key, {}).get(mbid)
        if decision:
            result = dict(decision)
            result['source'] = source
            result['source_mbid'] = mbid
            return result

    return (
        _lookup_artist_decision(snapshot, album_artist_mbids) or
        _lookup_artist_decision(snapshot, track_artist_mbids)
    )


def _lookup_aliases(snapshot, raw_terms: Iterable[str]):
    aliases = snapshot.get('aliases', {})
    genre_name: Optional[str] = None
    styles: List[str] = []
    seen_styles: Set[str] = set()
    for raw in raw_terms:
        row = aliases.get(raw.casefold())
        if not row:
            continue
        if row.get('genre') and not genre_name:
            genre_name = str(row['genre'])
        if row.get('style'):
            style = str(row['style'])
            if style.casefold() not in seen_styles:
                seen_styles.add(style.casefold())
                styles.append(style)
    if not genre_name and not styles:
        return None
    return {'genre': genre_name or '', 'styles': '; '.join(styles), 'source': 'alias', 'source_mbid': ''}


def _apply_metadata(metadata, decision) -> dict:
    genre = (decision.get('genre') or '').strip()
    styles = (decision.get('styles') or '').strip()
    force = OVERWRITE_WITH_DECISIONS and decision.get('source') != 'alias'
    result = {
        'genre': genre,
        'styles': styles,
        'force': force,
        'wrote_genre': False,
        'wrote_style': False,
        'wrote_grouping': False,
        'removed_style': False,
        'removed_contentgroup': False,
    }

    if genre and _should_write(metadata, 'genre', force):
        _set_tag(metadata, 'genre', genre)
        result['wrote_genre'] = True
    if WRITE_STYLE_TAG and styles and _should_write(metadata, 'style', force):
        _set_tag(metadata, 'style', styles)
        result['wrote_style'] = True
    if WRITE_GROUPING_TAG and styles and _should_write(metadata, 'grouping', force):
        _set_tag(metadata, 'grouping', styles)
        result['wrote_grouping'] = True
    if (
        REMOVE_DUPLICATE_STYLE_TAG and
        not WRITE_STYLE_TAG and
        styles and
        _same_semicolon_values(_get_tag(metadata, 'style', ''), styles)
    ):
        result['removed_style'] = _delete_tag(metadata, 'style')
    if styles and _same_semicolon_values(_get_tag(metadata, 'contentgroup', ''), styles):
        result['removed_contentgroup'] = _delete_tag(metadata, 'contentgroup')
    return result


def _process_metadata(metadata, entity_type: str) -> None:
    db_path = _taxonomy_db_path()
    json_path = _taxonomy_json_path()
    if not os.path.exists(db_path) and not os.path.exists(json_path):
        _append_file_log(f'taxonomy_missing db_path={db_path!r} json_path={json_path!r}')
        log.warning('Local Genre DB: taxonomy not found at %r or %r', db_path, json_path)
        return

    recording_mbid = _get_tag(metadata, 'musicbrainz_recordingid', '').strip()
    release_mbid = _get_tag(metadata, 'musicbrainz_albumid', '').strip()
    release_group_mbid = _get_tag(metadata, 'musicbrainz_releasegroupid', '').strip()
    album_artist_mbids = (
        _split_ids(_get_tag(metadata, 'musicbrainz_albumartistid', '')) or
        _split_ids(_get_tag(metadata, 'musicbrainz_releaseartistid', ''))
    )
    track_artist_mbids = _split_ids(_get_tag(metadata, 'musicbrainz_artistid', ''))

    try:
        snapshot = _load_snapshot()
        decision = _lookup_decision(
            snapshot,
            recording_mbid,
            release_mbid,
            release_group_mbid,
            album_artist_mbids,
            track_artist_mbids,
        )
        if not decision:
            decision = _lookup_aliases(snapshot, _collect_raw_terms(metadata))
        if decision:
            applied = _apply_metadata(metadata, decision)
        else:
            _append_pending_decision(
                metadata,
                recording_mbid,
                release_mbid,
                release_group_mbid,
                album_artist_mbids,
                track_artist_mbids,
            )
            applied = {}
        _append_file_log(
            'run '
            f'entity={entity_type!r} title={_get_tag(metadata, "title", "")!r} '
            f'artist={_get_tag(metadata, "artist", "")!r} '
            f'recording_mbid={recording_mbid!r} '
            f'release_mbid={release_mbid!r} '
            f'release_group_mbid={release_group_mbid!r} '
            f'album_artist_mbids={list(album_artist_mbids)!r} '
            f'track_artist_mbids={list(track_artist_mbids)!r} '
            f'source={(decision or {}).get("source", "")!r} '
            f'mbid={(decision or {}).get("source_mbid", "")!r} '
            f'genre={(applied or {}).get("genre", "")!r} '
            f'styles={(applied or {}).get("styles", "")!r} '
            f'force={int(bool((applied or {}).get("force")))} '
            f'wrote_genre={int(bool((applied or {}).get("wrote_genre")))} '
            f'wrote_style={int(bool((applied or {}).get("wrote_style")))} '
            f'wrote_grouping={int(bool((applied or {}).get("wrote_grouping")))} '
            f'removed_style={int(bool((applied or {}).get("removed_style")))} '
            f'removed_contentgroup={int(bool((applied or {}).get("removed_contentgroup")))}'
        )
    except Exception as exc:
        _append_file_log(f'processing_error={exc!r}')
        log.error('Local Genre DB: processing failed: %s', exc)


def process_album(tagger, metadata, release):
    _process_metadata(metadata, 'release')


def process_track(tagger, metadata, track, release):
    _process_metadata(metadata, 'recording')


def _log_plugin_load() -> None:
    _append_file_log('plugin import reached')
    db_path = _taxonomy_db_path()
    json_path = _taxonomy_json_path()
    _append_file_log(f'db_path={db_path!r} exists={os.path.exists(db_path)}')
    _append_file_log(f'json_path={json_path!r} exists={os.path.exists(json_path)}')
    try:
        snapshot = _load_snapshot()
        _append_file_log(
            'snapshot_loaded '
            f'artists={len(snapshot.get("artist_decisions", {}))} '
            f'releases={len(snapshot.get("release_decisions", {}))} '
            f'release_groups={len(snapshot.get("release_group_decisions", {}))} '
            f'recordings={len(snapshot.get("recording_decisions", {}))} '
            f'aliases={len(snapshot.get("aliases", {}))}'
        )
    except Exception as exc:
        _append_file_log(f'snapshot_load_error={exc!r}')


register_album_metadata_processor(process_album)
register_track_metadata_processor(process_track)
_log_plugin_load()
