#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Iterable

AUDIO_EXTENSIONS = {
    '.aac',
    '.aif',
    '.aiff',
    '.alac',
    '.ape',
    '.flac',
    '.m4a',
    '.m4b',
    '.mp3',
    '.mp4',
    '.mpc',
    '.oga',
    '.ogg',
    '.opus',
    '.tak',
    '.wav',
    '.wv',
}

OUTPUT_COLUMNS = [
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

TAG_ALIASES = {
    'title': ('title',),
    'artist': ('artist',),
    'album': ('album',),
    'albumartist': ('albumartist', 'album artist'),
    'date': ('date', 'originaldate', 'year'),
    'genre': ('genre',),
    'style': ('style',),
    'grouping': ('grouping',),
    'contentgroup': ('contentgroup', 'content group'),
    'musicbrainz_artistid': ('musicbrainz_artistid', 'musicbrainz artist id'),
    'musicbrainz_albumartistid': ('musicbrainz_albumartistid', 'musicbrainz album artist id'),
    'musicbrainz_releaseartistid': ('musicbrainz_releaseartistid', 'musicbrainz release artist id'),
    'musicbrainz_albumid': ('musicbrainz_albumid', 'musicbrainz album id', 'musicbrainz release id'),
    'musicbrainz_releasegroupid': ('musicbrainz_releasegroupid', 'musicbrainz release group id'),
    'musicbrainz_recordingid': ('musicbrainz_recordingid', 'musicbrainz recording id'),
    'musicbrainz_trackid': ('musicbrainz_trackid', 'musicbrainz track id'),
}

_LAST_PROGRESS_LEN = 0


def audio_files(root: Path) -> Iterable[Path]:
    for path in root.rglob('*'):
        if path.is_file() and path.suffix.casefold() in AUDIO_EXTENSIONS:
            yield path


def value_text(values: object) -> str:
    if values is None:
        return ''
    if isinstance(values, (list, tuple)):
        return '; '.join(str(value) for value in values if value)
    return str(values)


def get_tag(tags, output_name: str) -> str:
    aliases = TAG_ALIASES.get(output_name, (output_name,))
    for alias in aliases:
        try:
            value = tags.get(alias)
        except Exception:
            value = None
        text = value_text(value).strip()
        if text:
            return text
    return ''


def read_tags(path: Path) -> dict[str, str]:
    from mutagen import File

    tags = File(path, easy=True)
    row = {column: '' for column in OUTPUT_COLUMNS}
    row['path'] = str(path)
    if not tags:
        return row
    for column in OUTPUT_COLUMNS:
        if column != 'path':
            row[column] = get_tag(tags, column)
    return row


def print_progress(count: int, current_path: Path, started_at: float) -> None:
    global _LAST_PROGRESS_LEN

    spinner = '|/-\\'[count % 4]
    elapsed = max(time.monotonic() - started_at, 0.001)
    rate = count / elapsed
    display_name = current_path.name
    if len(display_name) > 60:
        display_name = display_name[:57] + '...'
    message = f'{spinner} scanned {count:,} files ({rate:,.1f}/sec): {display_name}'
    padding = ' ' * max(_LAST_PROGRESS_LEN - len(message), 0)
    print(f'\r{message}{padding}', end='', file=sys.stderr, flush=True)
    _LAST_PROGRESS_LEN = len(message)


def finish_progress(count: int, out_path: Path, started_at: float) -> None:
    global _LAST_PROGRESS_LEN

    elapsed = max(time.monotonic() - started_at, 0.001)
    message = f'Exported {count:,} files in {elapsed:,.1f}s to {out_path}'
    padding = ' ' * max(_LAST_PROGRESS_LEN - len(message), 0)
    print(f'\r{message}{padding}', file=sys.stderr)
    _LAST_PROGRESS_LEN = 0


def export_library(music_dir: Path, out_path: Path, limit: int | None, progress_every: int) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    started_at = time.monotonic()
    with out_path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for path in audio_files(music_dir):
            writer.writerow(read_tags(path))
            count += 1
            if progress_every > 0 and count % progress_every == 0:
                print_progress(count, path, started_at)
            if limit is not None and count >= limit:
                break
    if progress_every > 0:
        finish_progress(count, out_path, started_at)
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Export audio tags from a music directory to CSV')
    parser.add_argument('--music-dir', required=True, help='Root music directory to scan')
    parser.add_argument('--out', default='imports/library_export.csv', help='Output CSV path')
    parser.add_argument('--limit', type=int, help='Optional max files to scan for a test export')
    parser.add_argument('--progress-every', type=int, default=25, help='Print progress every N files, or 0 to disable')
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    music_dir = Path(args.music_dir).expanduser()
    out_path = Path(args.out)
    if not music_dir.exists():
        parser.error(f'Music directory does not exist: {music_dir}')
    if not music_dir.is_dir():
        parser.error(f'Not a directory: {music_dir}')

    try:
        count = export_library(music_dir, out_path, args.limit, args.progress_every)
    except ImportError:
        raise SystemExit('Missing dependency: install mutagen with "python -m pip install mutagen"')

    if args.progress_every == 0:
        print(f'Exported {count} files to {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
