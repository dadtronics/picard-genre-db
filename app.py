#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import manage_taxonomy as taxonomy


DB_PATH = 'taxonomy.db'
JSON_PATH = 'taxonomy.json'

SCOPES = {
    'artist': {
        'label': 'Artist',
        'hint': 'artist-wide default',
        'table': 'artist_decision',
        'id_column': 'artist_mbid',
        'command': taxonomy.decide_artist,
    },
    'release_group': {
        'label': 'Release Group',
        'hint': 'album/single/EP across versions',
        'table': 'release_group_decision',
        'id_column': 'release_group_mbid',
        'command': taxonomy.decide_release_group,
    },
    'release': {
        'label': 'Album/Release',
        'hint': 'one exact MusicBrainz release',
        'table': 'release_decision',
        'id_column': 'release_mbid',
        'command': taxonomy.decide_release,
    },
    'recording': {
        'label': 'Track',
        'hint': 'single recording override',
        'table': 'recording_decision',
        'id_column': 'recording_mbid',
        'command': taxonomy.decide_recording,
    },
}


def h(value: object) -> str:
    return html.escape(str(value or ''), quote=True)


def split_values(value: str | None) -> list[str]:
    return taxonomy.split_semicolon_values(value)


def clean(value: str | None) -> str:
    return taxonomy.sanitize_value(value)


def first_available_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise SystemExit(f'No free port found from {preferred} to {preferred + 99}')


def connect():
    con = taxonomy.connect(DB_PATH)
    taxonomy.ensure_schema(con)
    return con


def export_json(con) -> None:
    taxonomy.export_plugin_json(con, JSON_PATH)


def message_redirect(path: str, message: str, level: str = 'ok') -> str:
    query = urlencode({'message': message, 'level': level})
    sep = '&' if '?' in path else '?'
    return f'{path}{sep}{query}'


def post_error_redirect(path: str, form: dict[str, str], exc: BaseException) -> str:
    if path in ('/approve-import', '/dismiss-import'):
        return message_redirect(import_return_path(form), str(exc), 'error')
    if path == '/clear-import-source':
        return message_redirect('/imports', str(exc), 'error')
    if path in ('/save-decision', '/delete-decision'):
        return message_redirect('/decisions', str(exc), 'error')
    if path in ('/add-genre', '/add-style'):
        return message_redirect('/vocabulary', str(exc), 'error')
    return message_redirect(path or '/', str(exc), 'error')


class AppHandler(BaseHTTPRequestHandler):
    server_version = 'PicardGenreDB/0.1'

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write('%s - %s\n' % (self.address_string(), format % args))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == '/':
                self.html_response(self.render_home(parsed))
            elif parsed.path == '/decisions':
                self.html_response(self.render_decisions(parsed))
            elif parsed.path == '/vocabulary':
                self.html_response(self.render_vocabulary(parsed))
            elif parsed.path == '/imports':
                self.html_response(self.render_imports(parsed))
            else:
                self.not_found()
        except Exception as exc:
            self.html_response(self.render_error(exc), status=500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', '0') or '0')
        data = self.rfile.read(length).decode('utf-8')
        form = {key: values[-1] for key, values in parse_qs(data).items()}
        try:
            if parsed.path == '/save-decision':
                self.handle_save_decision(form)
            elif parsed.path == '/delete-decision':
                self.handle_delete_decision(form)
            elif parsed.path == '/add-genre':
                self.handle_add_genre(form)
            elif parsed.path == '/add-style':
                self.handle_add_style(form)
            elif parsed.path == '/delete-style':
                self.handle_delete_style(form)
            elif parsed.path == '/split-style':
                self.handle_split_style(form)
            elif parsed.path == '/export-json':
                self.handle_export_json()
            elif parsed.path == '/approve-import':
                self.handle_approve_import(form)
            elif parsed.path == '/dismiss-import':
                self.handle_dismiss_import(form)
            elif parsed.path == '/clear-import-source':
                self.handle_clear_import_source(form)
            else:
                self.not_found()
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            self.redirect(post_error_redirect(parsed.path, form, exc))

    def html_response(self, body: str, status: int = 200) -> None:
        data = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header('Location', location)
        self.end_headers()

    def not_found(self) -> None:
        self.html_response(self.page('Not Found', '<p>Not found.</p>'), status=404)

    def render_error(self, exc: Exception) -> str:
        return self.page('Error', f'<div class="alert error">{h(exc)}</div>')

    def handle_save_decision(self, form: dict[str, str]) -> None:
        scope = form.get('scope', 'release_group')
        if scope not in SCOPES:
            raise ValueError(f'Unknown scope: {scope}')
        mbid = clean(form.get('mbid', ''))
        genre = taxonomy.normalize_manual_list_text(form.get('genre', ''))
        styles = normalize_joined_values(form.get('styles', ''))
        notes = clean(form.get('notes', '')) or None
        locked = form.get('locked') == '1'
        if not mbid:
            raise ValueError('MBID is required.')
        if not genre:
            raise ValueError('Genre is required.')

        con = connect()
        try:
            SCOPES[scope]['command'](con, mbid, genre, styles, notes, locked, True)
            export_json(con)
        finally:
            con.close()
        self.redirect(message_redirect('/decisions', f'{SCOPES[scope]["label"]} decision saved.'))

    def handle_delete_decision(self, form: dict[str, str]) -> None:
        scope = form.get('scope', '')
        mbid = clean(form.get('mbid', ''))
        if scope not in SCOPES or not mbid:
            raise ValueError('Scope and MBID are required.')
        table = SCOPES[scope]['table']
        id_column = SCOPES[scope]['id_column']
        con = connect()
        try:
            con.execute(f'DELETE FROM {table} WHERE {id_column} = ?', (mbid,))
            con.commit()
            export_json(con)
        finally:
            con.close()
        self.redirect(message_redirect('/decisions', 'Decision deleted.'))

    def handle_add_genre(self, form: dict[str, str]) -> None:
        name = clean(form.get('name', ''))
        if not name:
            raise ValueError('Genre name is required.')
        con = connect()
        try:
            taxonomy.add_genre(con, name)
            export_json(con)
        finally:
            con.close()
        self.redirect(message_redirect('/vocabulary', f'Genre added: {name}'))

    def handle_add_style(self, form: dict[str, str]) -> None:
        genre = clean(form.get('genre', ''))
        style = clean(form.get('style', ''))
        if not genre or not style:
            raise ValueError('Genre and style are required.')
        con = connect()
        try:
            taxonomy.add_style(con, genre, style)
            export_json(con)
        finally:
            con.close()
        self.redirect(message_redirect('/vocabulary', f'Style added: {style}'))

    def handle_delete_style(self, form: dict[str, str]) -> None:
        style = clean(form.get('style', ''))
        if not style:
            raise ValueError('Style is required.')
        con = connect()
        try:
            deleted = delete_style(con, style)
            export_json(con)
        finally:
            con.close()
        self.redirect(message_redirect('/vocabulary', f'Deleted style: {style}' if deleted else f'Style not found: {style}'))

    def handle_split_style(self, form: dict[str, str]) -> None:
        genre = clean(form.get('genre', ''))
        style = clean(form.get('style', ''))
        parts = taxonomy.normalize_manual_list_text(form.get('parts', ''))
        if not genre or not style or not parts:
            raise ValueError('Genre, style, and replacement parts are required.')
        con = connect()
        try:
            for part in split_values(parts):
                taxonomy.add_style(con, genre, part)
            delete_style(con, style)
            export_json(con)
        finally:
            con.close()
        self.redirect(message_redirect('/vocabulary', f'Split style: {style}'))

    def handle_export_json(self) -> None:
        con = connect()
        try:
            export_json(con)
        finally:
            con.close()
        self.redirect(message_redirect('/', 'taxonomy.json refreshed.'))

    def handle_approve_import(self, form: dict[str, str]) -> None:
        source = clean(form.get('source', ''))
        scope = clean(form.get('scope', 'release_group'))
        mbid = clean(form.get('mbid', ''))
        original_scope = clean(form.get('return_scope', scope))
        query = clean(form.get('q', ''))
        limit = clean(form.get('limit', '100'))
        target = clean(form.get('target', ''))
        if target:
            scope, mbid = parse_import_target(target)
        genre = taxonomy.normalize_manual_list_text(form.get('genre', ''))
        styles = normalize_joined_values(form.get('styles', ''))
        if scope not in SCOPES:
            raise ValueError(f'Unknown scope: {scope}')
        if not source or not mbid or not genre:
            raise ValueError('Source, MBID, and genre are required.')
        con = connect()
        try:
            SCOPES[scope]['command'](con, mbid, genre, styles, None, False, True)
            export_json(con)
        finally:
            con.close()
        return_params = {
            'source': source,
            'scope': original_scope if original_scope in SCOPES else scope,
            'limit': limit or '100',
        }
        if query:
            return_params['q'] = query
        path = f'/imports?{urlencode(return_params)}'
        self.redirect(message_redirect(path, 'Imported decision approved.'))

    def handle_dismiss_import(self, form: dict[str, str]) -> None:
        source = clean(form.get('source', ''))
        scope = clean(form.get('scope', 'release_group'))
        mbid = clean(form.get('mbid', ''))
        genre = taxonomy.normalize_manual_list_text(form.get('genre', ''))
        styles = normalize_joined_values(form.get('styles', ''))
        if scope not in SCOPES:
            raise ValueError(f'Unknown scope: {scope}')
        if not source or not mbid:
            raise ValueError('Source and MBID are required.')
        con = connect()
        try:
            deleted = delete_import_candidate(con, source, scope, mbid, genre, styles)
        finally:
            con.close()
        self.redirect(message_redirect(import_return_path(form), f'Dismissed {deleted} imported tracks.'))

    def handle_clear_import_source(self, form: dict[str, str]) -> None:
        source = clean(form.get('source', ''))
        if not source:
            raise ValueError('Source is required.')
        con = connect()
        try:
            cur = con.execute('DELETE FROM library_tag_import WHERE import_source = ?', (source,))
            con.commit()
            deleted = cur.rowcount if cur.rowcount is not None else 0
        finally:
            con.close()
        self.redirect(message_redirect('/imports', f'Cleared {deleted} imported tracks from {source}.'))

    def render_home(self, parsed) -> str:
        con = connect()
        try:
            counts = {
                'genres': scalar(con, 'SELECT COUNT(*) FROM canonical_genre'),
                'styles': scalar(con, 'SELECT COUNT(*) FROM canonical_style'),
                'artists': scalar(con, 'SELECT COUNT(*) FROM artist_decision'),
                'albums': scalar(con, 'SELECT COUNT(*) FROM release_group_decision'),
                'releases': scalar(con, 'SELECT COUNT(*) FROM release_decision'),
                'tracks': scalar(con, 'SELECT COUNT(*) FROM recording_decision'),
                'aliases': scalar(con, 'SELECT COUNT(*) FROM alias_mapping'),
            }
            recent = recent_decisions(con, 8)
        finally:
            con.close()

        cards = ''.join(
            f'<div class="metric"><span>{h(label)}</span><strong>{count}</strong></div>'
            for label, count in (
                ('Genres', counts['genres']),
                ('Styles', counts['styles']),
                ('Artist Decisions', counts['artists']),
                ('Album Decisions', counts['albums']),
                ('Release Decisions', counts['releases']),
                ('Track Decisions', counts['tracks']),
                ('Aliases', counts['aliases']),
            )
        )
        recent_rows = ''.join(decision_row(row) for row in recent) or '<tr><td colspan="7">No decisions yet.</td></tr>'
        content = f'''
            {self.alert(parsed)}
            <section class="toolbar">
              <a class="button primary" href="/decisions">Add Decision</a>
              <a class="button" href="/imports">Review Imports</a>
              <a class="button" href="/vocabulary">Vocabulary</a>
              <form method="post" action="/export-json"><button type="submit">Refresh JSON</button></form>
            </section>
            <section class="metrics">{cards}</section>
            <section>
              <h2>Recent Decisions</h2>
              <table class="import-table">
                <thead><tr><th>Scope</th><th>Name</th><th>MBID</th><th>Genre</th><th>Grouping</th><th>Updated</th><th></th></tr></thead>
                <tbody>{recent_rows}</tbody>
              </table>
            </section>
        '''
        return self.page('Picard Genre DB', content, active='home')

    def render_decisions(self, parsed) -> str:
        query = parse_qs(parsed.query)
        edit_scope = query.get('scope', ['release_group'])[0]
        edit_mbid = query.get('mbid', [''])[0]
        filter_scope = query.get('filter_scope', ['all'])[0]
        q = query.get('q', [''])[0].strip()
        if filter_scope != 'all' and filter_scope not in SCOPES:
            filter_scope = 'all'

        con = connect()
        try:
            genres = fetch_genres(con)
            styles = fetch_styles(con)
            decision = fetch_decision(con, edit_scope, edit_mbid) if edit_mbid else None
            rows = recent_decisions(con, 200, filter_scope, q)
            counts = decision_counts(con)
        finally:
            con.close()

        scope_options = ''.join(
            option(scope, scope_label(config), (decision or {}).get('scope', edit_scope) == scope)
            for scope, config in SCOPES.items()
        )
        genre_options = ''.join(f'<option value="{h(name)}">' for name in genres)
        style_options = ''.join(f'<option value="{h(name)}">' for _, name in styles)
        table_rows = ''.join(decision_row(row, with_edit=True) for row in rows) or '<tr><td colspan="7">No decisions yet.</td></tr>'
        filter_options = option('all', f'All ({sum(counts.values())})', filter_scope == 'all') + ''.join(
            option(scope, f'{config["label"]} ({counts.get(scope, 0)})', filter_scope == scope)
            for scope, config in SCOPES.items()
        )
        content = f'''
            {self.alert(parsed)}
            <section class="split">
              <form class="panel" method="post" action="/save-decision">
                <h2>{'Edit' if decision else 'Add'} Decision</h2>
                <label>Scope
                  <select name="scope">{scope_options}</select>
                </label>
                <label>MusicBrainz ID
                  <input name="mbid" value="{h((decision or {}).get('mbid', edit_mbid))}" required>
                </label>
                <label>Genre
                  <input name="genre" list="genres" value="{h((decision or {}).get('genre', ''))}" placeholder="Electronic; Pop/Rock" required>
                </label>
                <label>Grouping / Styles
                  <textarea name="styles" rows="4" list="styles" placeholder="House; Techno">{h((decision or {}).get('styles', ''))}</textarea>
                </label>
                <label>Notes
                  <input name="notes" value="{h((decision or {}).get('notes', ''))}">
                </label>
                <label class="check"><input type="checkbox" name="locked" value="1" {'checked' if (decision or {}).get('locked') else ''}> Locked</label>
                <div class="actions">
                  <button type="submit">Save Decision</button>
                  <a class="button" href="/decisions">Clear</a>
                </div>
                <datalist id="genres">{genre_options}</datalist>
                <datalist id="styles">{style_options}</datalist>
              </form>
              <aside class="panel">
                <h2>Scope Cheat Sheet</h2>
                <p><strong>Artist</strong> for artist-page defaults.</p>
                <p><strong>Release Group</strong> for album, single, EP, or mix pages across versions.</p>
                <p><strong>Album/Release</strong> for one exact MusicBrainz release.</p>
                <p><strong>Track</strong> for one-song overrides.</p>
              </aside>
            </section>
            <section>
              <h2>Decisions</h2>
              <form class="filters" method="get" action="/decisions">
                <label>Show
                  <select name="filter_scope">{filter_options}</select>
                </label>
                <label>Search
                  <input name="q" value="{h(q)}" placeholder="artist, album, style, MBID">
                </label>
                <button type="submit">Filter</button>
              </form>
              <table>
                <thead><tr><th>Scope</th><th>Name</th><th>MBID</th><th>Genre</th><th>Grouping</th><th>Updated</th><th></th></tr></thead>
                <tbody>{table_rows}</tbody>
              </table>
            </section>
        '''
        return self.page('Decisions', content, active='decisions')

    def render_vocabulary(self, parsed) -> str:
        con = connect()
        try:
            genres = fetch_genres(con)
            styles = fetch_styles(con)
            suspicious = suspicious_styles(styles)
        finally:
            con.close()
        genre_options = ''.join(option(name, name, False) for name in genres)
        style_rows = ''.join(
            f'<tr><td>{h(genre)}</td><td>{h(style)}</td></tr>'
            for genre, style in styles
        )
        suspicious_rows = ''.join(vocabulary_cleanup_row(genre, style) for genre, style in suspicious)
        if not suspicious_rows:
            suspicious_rows = '<tr><td colspan="4">No suspicious styles found.</td></tr>'
        content = f'''
            {self.alert(parsed)}
            <section class="split">
              <form class="panel" method="post" action="/add-genre">
                <h2>Add Genre</h2>
                <label>Name <input name="name" required></label>
                <button type="submit">Add Genre</button>
              </form>
              <form class="panel" method="post" action="/add-style">
                <h2>Add Style</h2>
                <label>Genre <select name="genre">{genre_options}</select></label>
                <label>Style <input name="style" required></label>
                <button type="submit">Add Style</button>
              </form>
            </section>
            <section>
              <h2>Suspicious Styles</h2>
              <p class="muted">These look like combined import values. Split preserves slash terms like Pop/Rock and Alternative/Indie Rock where possible.</p>
              <table>
                <thead><tr><th>Genre</th><th>Style</th><th>Split Into</th><th></th></tr></thead>
                <tbody>{suspicious_rows}</tbody>
              </table>
            </section>
            <section>
              <h2>Styles</h2>
              <table>
                <thead><tr><th>Genre</th><th>Style</th></tr></thead>
                <tbody>{style_rows}</tbody>
              </table>
            </section>
        '''
        return self.page('Vocabulary', content, active='vocabulary')

    def render_imports(self, parsed) -> str:
        query = parse_qs(parsed.query)
        source = query.get('source', ['main_library'])[0]
        scope = query.get('scope', ['release_group'])[0]
        if scope not in SCOPES:
            scope = 'release_group'
        limit = int(query.get('limit', ['100'])[0] or '100')
        q = query.get('q', [''])[0].strip()
        show_existing = query.get('show_existing', [''])[0] == '1'

        con = connect()
        try:
            sources = import_sources(con)
            genres = fetch_genres(con)
            candidates = import_candidates(con, source, scope, q, limit, show_existing)
        finally:
            con.close()

        source_options = ''.join(option(item, item, item == source) for item in sources)
        scope_options = ''.join(option(key, scope_label(value), key == scope) for key, value in SCOPES.items())
        genre_options = ''.join(f'<option value="{h(name)}">' for name in genres)
        rows = ''.join(import_candidate_row(row, source, scope, q, limit, show_existing, genre_options) for row in candidates)
        if not rows:
            rows = '<p class="muted">No import candidates found.</p>'

        content = f'''
            {self.alert(parsed)}
            <section>
              <h2>Review Imports</h2>
              <form class="filters" method="get" action="/imports">
                <label>Source
                  <select name="source">{source_options}</select>
                </label>
                <label>Approve As
                  <select name="scope">{scope_options}</select>
                </label>
                <label>Search
                  <input name="q" value="{h(q)}" placeholder="artist, album, title, MBID">
                </label>
                <label>Limit
                  <input name="limit" type="number" min="1" max="500" value="{h(limit)}">
                </label>
                <label class="check filter-check"><input type="checkbox" name="show_existing" value="1" {'checked' if show_existing else ''}> Show existing</label>
                <button type="submit">Filter</button>
              </form>
              <form class="danger-form" method="post" action="/clear-import-source" onsubmit="return confirm('Clear all imported rows for this source? Decisions will not be deleted.');">
                <input type="hidden" name="source" value="{h(source)}">
                <button class="danger-button" type="submit">Clear Source</button>
              </form>
            </section>
            <section>
              <div class="import-list">{rows}</div>
            </section>
            <datalist id="genres">{genre_options}</datalist>
        '''
        return self.page('Review Imports', content, active='imports')

    def alert(self, parsed) -> str:
        query = parse_qs(parsed.query)
        message = query.get('message', [''])[0]
        level = query.get('level', ['ok'])[0]
        if not message:
            return ''
        return f'<div class="alert {h(level)}">{h(message)}</div>'

    def page(self, title: str, content: str, active: str = '') -> str:
        return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <header>
    <h1>Picard Genre DB</h1>
    <nav>
      {nav_link('/', 'Home', active == 'home')}
      {nav_link('/decisions', 'Decisions', active == 'decisions')}
      {nav_link('/imports', 'Imports', active == 'imports')}
      {nav_link('/vocabulary', 'Vocabulary', active == 'vocabulary')}
    </nav>
  </header>
  <main>{content}</main>
</body>
</html>'''


def nav_link(url: str, label: str, selected: bool) -> str:
    cls = 'active' if selected else ''
    return f'<a class="{cls}" href="{h(url)}">{h(label)}</a>'


def scope_label(config: dict[str, str]) -> str:
    return f'{config["label"]} - {config["hint"]}'


def option(value: str, label: str, selected: bool) -> str:
    return f'<option value="{h(value)}" {"selected" if selected else ""}>{h(label)}</option>'


def urlencode_value(value: str) -> str:
    return urlencode({'v': value})[2:]


def scalar(con, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


def fetch_genres(con) -> list[str]:
    return [
        str(row['name'])
        for row in con.execute('SELECT name FROM canonical_genre ORDER BY name')
    ]


def fetch_styles(con) -> list[tuple[str, str]]:
    return [
        (str(row['genre']), str(row['style']))
        for row in con.execute(
            '''
            SELECT cg.name AS genre, cs.name AS style
            FROM canonical_style cs
            JOIN canonical_genre cg ON cg.id = cs.genre_id
            ORDER BY cg.name, cs.name
            '''
        )
    ]


def delete_style(con, style: str) -> int:
    cur = con.execute('DELETE FROM canonical_style WHERE name = ?', (style,))
    con.commit()
    return cur.rowcount if cur.rowcount is not None else 0


PROTECTED_SLASH_TERMS = (
    'Adult Alternative Pop/Rock',
    'Alternative Pop/Rock',
    'Alternative/Indie Rock',
    'Club/Dance',
    'Comedy/Spoken',
    'Contemporary Pop/Rock',
    'Contemporary Singer/Songwriter',
    'Early Pop/Rock',
    "Jungle/Drum'n'Bass",
    'Nashville Sound/Countrypolitan',
    'Orchestral/Easy Listening',
    'Pop/Rock',
    'Psychedelic/Garage',
    'Punk/New Wave',
    'Singer/Songwriter',
)


def suspicious_styles(styles: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [
        (genre, style)
        for genre, style in styles
        if suggested_style_split(style)
    ]


def suggested_style_split(style: str) -> list[str]:
    placeholders: dict[str, str] = {}
    text = style
    for index, term in enumerate(sorted(PROTECTED_SLASH_TERMS, key=len, reverse=True)):
        token = f'@@{index}@@'
        if term in text:
            placeholders[token] = term
            text = text.replace(term, token)
    if '/' not in text and ',' not in text:
        return []
    raw_parts = []
    for part in text.replace(',', '/').split('/'):
        part = part.strip()
        if not part:
            continue
        for token, term in placeholders.items():
            part = part.replace(token, term)
        raw_parts.append(part)
    parts = unique_names(raw_parts)
    if len(parts) <= 1 or parts == [style]:
        return []
    return parts


def vocabulary_cleanup_row(genre: str, style: str) -> str:
    parts = '; '.join(suggested_style_split(style))
    return f'''
      <tr>
        <td>{h(genre)}</td>
        <td>{h(style)}</td>
        <td>
          <form id="{h('split-' + style)}" method="post" action="/split-style">
            <input type="hidden" name="genre" value="{h(genre)}">
            <input type="hidden" name="style" value="{h(style)}">
            <input name="parts" value="{h(parts)}">
          </form>
        </td>
        <td>
          <div class="row-actions">
            <button form="{h('split-' + style)}" type="submit">Split</button>
            <form method="post" action="/delete-style" onsubmit="return confirm('Delete this vocabulary style? Existing decisions are not edited.');">
              <input type="hidden" name="style" value="{h(style)}">
              <button class="link" type="submit">Delete</button>
            </form>
          </div>
        </td>
      </tr>
    '''


def fetch_decision(con, scope: str, mbid: str) -> dict | None:
    if scope not in SCOPES or not mbid:
        return None
    config = SCOPES[scope]
    row = con.execute(
        f'''
        SELECT
            d.{config['id_column']} AS mbid,
            COALESCE(NULLIF(d.genres_text, ''), cg.name) AS genre,
            d.styles_text AS styles,
            d.notes AS notes,
            d.locked AS locked,
            d.updated_at AS updated_at
        FROM {config['table']} d
        JOIN canonical_genre cg ON cg.id = d.normalized_genre_id
        WHERE d.{config['id_column']} = ?
        ''',
        (mbid,),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    result['scope'] = scope
    return result


def decision_counts(con) -> dict[str, int]:
    return {
        scope: scalar(con, f'SELECT COUNT(*) FROM {config["table"]}')
        for scope, config in SCOPES.items()
    }


def recent_decisions(con, limit: int, scope_filter: str = 'all', query: str = '') -> list[dict]:
    selects = []
    scopes = SCOPES.items()
    if scope_filter != 'all' and scope_filter in SCOPES:
        scopes = [(scope_filter, SCOPES[scope_filter])]
    for scope, config in scopes:
        selects.append(
            f'''
            SELECT
                '{scope}' AS scope,
                '{config['label']}' AS scope_label,
                d.{config['id_column']} AS mbid,
                COALESCE(NULLIF(d.genres_text, ''), cg.name) AS genre,
                d.styles_text AS styles,
                d.updated_at AS updated_at
            FROM {config['table']} d
            JOIN canonical_genre cg ON cg.id = d.normalized_genre_id
            '''
        )
    sql_limit = max(limit, 1000) if query else limit
    sql = ' UNION ALL '.join(selects) + ' ORDER BY updated_at DESC LIMIT ?'
    decisions = [dict(row) for row in con.execute(sql, (sql_limit,))]
    for row in decisions:
        names = decision_display_names(con, str(row['scope']), str(row['mbid']))
        row['display_name'] = names[0] if names else ''
        row['alternate_names'] = names[1:]
    if query:
        needle = query.casefold()
        decisions = [
            row for row in decisions
            if needle in decision_search_text(row).casefold()
        ][:limit]
    return decisions


def decision_search_text(row: dict) -> str:
    alternate_names = ' '.join(str(name) for name in row.get('alternate_names', []))
    return ' '.join(
        str(row.get(key) or '')
        for key in ('scope_label', 'mbid', 'genre', 'styles', 'display_name')
    ) + ' ' + alternate_names


def decision_display_name(con, scope: str, mbid: str) -> str:
    names = decision_display_names(con, scope, mbid)
    return names[0] if names else ''


def decision_display_names(con, scope: str, mbid: str, limit: int = 5) -> list[str]:
    if not mbid:
        return []
    if scope == 'artist':
        row = con.execute(
            '''
            SELECT name, SUM(seen) AS total_seen, MIN(priority) AS best_priority
            FROM (
                SELECT COALESCE(NULLIF(artist, ''), NULLIF(albumartist, '')) AS name, COUNT(*) AS seen, 1 AS priority
                FROM library_tag_import
                WHERE musicbrainz_artistid = ?
                GROUP BY name
                UNION ALL
                SELECT COALESCE(NULLIF(artist, ''), NULLIF(albumartist, '')) AS name, COUNT(*) AS seen, 2 AS priority
                FROM library_tag_import
                WHERE musicbrainz_releaseartistid = ?
                GROUP BY name
                UNION ALL
                SELECT COALESCE(NULLIF(albumartist, ''), NULLIF(artist, '')) AS name, COUNT(*) AS seen, 3 AS priority
                FROM library_tag_import
                WHERE musicbrainz_albumartistid = ?
                GROUP BY name
            )
            WHERE name IS NOT NULL AND name != ''
            GROUP BY name
            ORDER BY best_priority, total_seen DESC, name
            LIMIT 1
            ''',
            (mbid, mbid, mbid),
        ).fetchone()
        return [str(row['name'] or '')] if row else []
    if scope == 'release_group':
        rows = con.execute(
            '''
            SELECT
                COALESCE(NULLIF(albumartist, ''), NULLIF(artist, '')) AS artist_name,
                album,
                COUNT(*) AS seen
            FROM library_tag_import
            WHERE musicbrainz_releasegroupid = ?
            GROUP BY artist_name, album
            ORDER BY seen DESC, artist_name, album
            LIMIT ?
            ''',
            (mbid, limit),
        ).fetchall()
        return unique_names(joined_name(row, 'artist_name', 'album') for row in rows)
    if scope == 'release':
        rows = con.execute(
            '''
            SELECT
                COALESCE(NULLIF(albumartist, ''), NULLIF(artist, '')) AS artist_name,
                album,
                COUNT(*) AS seen
            FROM library_tag_import
            WHERE musicbrainz_albumid = ?
            GROUP BY artist_name, album
            ORDER BY seen DESC, artist_name, album
            LIMIT ?
            ''',
            (mbid, limit),
        ).fetchall()
        return unique_names(joined_name(row, 'artist_name', 'album') for row in rows)
    if scope == 'recording':
        rows = con.execute(
            '''
            SELECT artist, title, COUNT(*) AS seen
            FROM library_tag_import
            WHERE musicbrainz_recordingid = ?
            GROUP BY artist, title
            ORDER BY seen DESC, artist, title
            LIMIT ?
            ''',
            (mbid, limit),
        ).fetchall()
        return unique_names(joined_name(row, 'artist', 'title') for row in rows)
    return []


def unique_names(names) -> list[str]:
    result = []
    seen = set()
    for name in names:
        clean_name = str(name or '').strip()
        key = clean_name.casefold()
        if not clean_name or key in seen:
            continue
        seen.add(key)
        result.append(clean_name)
    return result


def joined_name(row, first_key: str, second_key: str) -> str:
    first = str(row[first_key] or '').strip()
    second = str(row[second_key] or '').strip()
    if first and second:
        return f'{first} - {second}'
    return first or second


def import_sources(con) -> list[str]:
    rows = con.execute(
        '''
        SELECT import_source, COUNT(*) AS tracks
        FROM library_tag_import
        GROUP BY import_source
        ORDER BY import_source
        '''
    ).fetchall()
    return [str(row['import_source']) for row in rows] or ['main_library']


def import_candidates(con, source: str, scope: str, query: str, limit: int, show_existing: bool = False) -> list[dict]:
    where = [
        'import_source = ?',
        "raw_genre != ''",
        "COALESCE(NULLIF(raw_grouping, ''), raw_style) != ''",
    ]
    params: list[object] = [source]
    if query:
        like = f'%{query}%'
        where.append(
            '''
            (
              title LIKE ? OR artist LIKE ? OR album LIKE ? OR albumartist LIKE ?
              OR musicbrainz_artistid LIKE ? OR musicbrainz_albumartistid LIKE ?
              OR musicbrainz_albumid LIKE ? OR musicbrainz_releasegroupid LIKE ?
              OR musicbrainz_recordingid LIKE ?
            )
            '''
        )
        params.extend([like] * 9)

    rows = con.execute(
        f'''
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
        WHERE {' AND '.join(where)}
        ''',
        tuple(params),
    ).fetchall()

    candidates: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        mbid = taxonomy.target_mbid_for_scope(row, scope)
        if not mbid:
            continue
        genre = normalized_import_genre(con, row['raw_genre'])
        styles = '; '.join(split_values(row['raw_grouping'] or row['raw_style']))
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
                'title': row['title'] or '',
                'album_artist_mbid': row['musicbrainz_albumartistid'] or '',
                'release_artist_mbid': row['musicbrainz_releaseartistid'] or '',
                'track_artist_mbid': row['musicbrainz_artistid'] or '',
                'artist_mbid': mbid if scope == 'artist' else (
                    row['musicbrainz_albumartistid']
                    or row['musicbrainz_releaseartistid']
                    or row['musicbrainz_artistid']
                    or ''
                ),
                'release_group_mbid': row['musicbrainz_releasegroupid'] or '',
                'release_mbid': row['musicbrainz_albumid'] or '',
                'recording_mbid': row['musicbrainz_recordingid'] or '',
            },
        )
        candidate['tracks'] += 1

    existing = existing_decision_keys(con, scope)
    result = []
    for item in candidates.values():
        item['exists'] = item['mbid'] in existing
        if item['exists'] and not show_existing:
            continue
        result.append(item)
    result.sort(
        key=lambda item: (
            bool(item['exists']),
            -int(item['tracks']),
            str(item['albumartist']).casefold(),
            str(item['album']).casefold(),
            str(item['artist']).casefold(),
        )
    )
    return result[:limit]


def existing_decision_keys(con, scope: str) -> set[str]:
    if scope not in SCOPES:
        return set()
    config = SCOPES[scope]
    return {
        str(row['mbid'])
        for row in con.execute(
            f'SELECT {config["id_column"]} AS mbid FROM {config["table"]}'
        )
    }


def decision_row(row: dict, with_edit: bool = False) -> str:
    edit = ''
    names = [str(name) for name in row.get('alternate_names', []) if name]
    name_hint = ''
    if names:
        visible = '; '.join(names[:3])
        more = len(names) - 3
        suffix = f' (+{more} more)' if more > 0 else ''
        name_hint = f'<span class="hint">Also: {h(visible)}{h(suffix)}</span>'
    if with_edit:
        edit = f'''
          <div class="row-actions">
            <a href="/decisions?scope={h(row['scope'])}&mbid={h(row['mbid'])}">Edit</a>
            <form method="post" action="/delete-decision">
              <input type="hidden" name="scope" value="{h(row['scope'])}">
              <input type="hidden" name="mbid" value="{h(row['mbid'])}">
              <button class="link" type="submit">Delete</button>
            </form>
          </div>
        '''
    return f'''
      <tr>
        <td>{scope_badge(str(row.get('scope', '')))}</td>
        <td>{h(row.get('display_name') or 'Unknown')}{name_hint}</td>
        <td><code>{h(row.get('mbid'))}</code></td>
        <td>{h(row.get('genre'))}</td>
        <td>{h(row.get('styles'))}</td>
        <td>{h(row.get('updated_at'))}</td>
        <td>{edit}</td>
      </tr>
    '''


def scope_badge(scope: str) -> str:
    config = SCOPES.get(scope)
    if not config:
        return h(scope)
    return (
        f'<span class="badge">{h(config["label"])}</span>'
        f'<span class="hint">{h(config["hint"])}</span>'
    )


def import_candidate_row(
    row: dict,
    source: str,
    scope: str,
    query: str,
    limit: int,
    show_existing: bool,
    genre_options: str,
) -> str:
    existing = 'Yes' if row.get('exists') else ''
    disabled = 'disabled' if row.get('exists') else ''
    form_id = import_form_id(row, scope)
    target_options = import_target_options(row, scope)
    label = (
        f'<strong>{h(row.get("albumartist") or row.get("artist"))}</strong>'
        f'<br>{h(row.get("album"))}'
    )
    if scope in ('recording', 'track'):
        label += f'<br><span class="muted">{h(row.get("title"))}</span>'
    ids = import_id_block(row, scope)
    status = (
        f'<a class="badge" href="/decisions?scope={h(scope)}&mbid={h(row.get("mbid"))}">Existing</a>'
        if existing else ''
    )
    return f'''
      <article class="import-card">
        <div class="import-summary">
          <div class="track-count">{h(row.get('tracks'))}<span>tracks</span></div>
          <div>{label}</div>
          <div class="approve-actions">
            {status}
            <form id="{h(form_id)}" method="post" action="/approve-import">
              <input type="hidden" name="source" value="{h(source)}">
              <input type="hidden" name="scope" value="{h(scope)}">
              <input type="hidden" name="return_scope" value="{h(scope)}">
              <input type="hidden" name="q" value="{h(query)}">
              <input type="hidden" name="limit" value="{h(limit)}">
              <input type="hidden" name="show_existing" value="{h('1' if show_existing else '')}">
              <input type="hidden" name="mbid" value="{h(row.get('mbid'))}">
              <button type="submit" {disabled}>Approve</button>
            </form>
            <form method="post" action="/dismiss-import" onsubmit="return confirm('Dismiss this import candidate? This only removes staging rows.');">
              <input type="hidden" name="source" value="{h(source)}">
              <input type="hidden" name="scope" value="{h(scope)}">
              <input type="hidden" name="q" value="{h(query)}">
              <input type="hidden" name="limit" value="{h(limit)}">
              <input type="hidden" name="show_existing" value="{h('1' if show_existing else '')}">
              <input type="hidden" name="mbid" value="{h(row.get('mbid'))}">
              <input type="hidden" name="genre" value="{h(row.get('genre'))}">
              <input type="hidden" name="styles" value="{h(row.get('styles'))}">
              <button class="secondary-button" type="submit">Dismiss</button>
            </form>
          </div>
        </div>
        <div class="import-fields">
          <label class="compact-label">Approve Target
            <select name="target" form="{h(form_id)}" {disabled}>{target_options}</select>
          </label>
          <label class="compact-label">Genre
            <input name="genre" form="{h(form_id)}" list="genres" value="{h(row.get('genre'))}" {disabled}>
          </label>
          <div class="id-panel">{ids}</div>
        </div>
        <label class="compact-label grouping-editor">Grouping
          <textarea name="styles" form="{h(form_id)}" rows="5" {disabled}>{h(row.get('styles'))}</textarea>
        </label>
      </article>
    '''


def import_form_id(row: dict, scope: str) -> str:
    base = f'{scope}-{row.get("mbid", "")}-{row.get("genre", "")}-{row.get("styles", "")}'
    return 'import-' + ''.join(char if char.isalnum() else '-' for char in base)[:80]


def import_target_options(row: dict, selected_scope: str) -> str:
    options: list[tuple[str, str, str]] = []
    add_target_options(options, 'artist', 'Artist', row.get('album_artist_mbid'))
    add_target_options(options, 'artist', 'Artist', row.get('release_artist_mbid'))
    add_target_options(options, 'artist', 'Artist', row.get('track_artist_mbid'))
    add_target_options(options, 'release_group', 'Release Group', row.get('release_group_mbid'))
    add_target_options(options, 'release', 'Album/Release', row.get('release_mbid'))
    add_target_options(options, 'recording', 'Track', row.get('recording_mbid'))

    seen: set[tuple[str, str]] = set()
    unique = []
    for scope, label, mbid in options:
        key = (scope, mbid)
        if key in seen:
            continue
        seen.add(key)
        unique.append((scope, label, mbid))

    selected_value = f'{selected_scope}|{row.get("mbid")}'
    return ''.join(
        option(f'{scope}|{mbid}', f'{label}: {mbid}', f'{scope}|{mbid}' == selected_value)
        for scope, label, mbid in unique
    )


def import_return_path(form: dict[str, str]) -> str:
    source = clean(form.get('source', ''))
    scope = clean(form.get('scope', 'release_group'))
    query = clean(form.get('q', ''))
    limit = clean(form.get('limit', '100')) or '100'
    params = {
        'source': source,
        'scope': scope if scope in SCOPES else 'release_group',
        'limit': limit,
    }
    if query:
        params['q'] = query
    if clean(form.get('show_existing', '')) == '1':
        params['show_existing'] = '1'
    return f'/imports?{urlencode(params)}'


def delete_import_candidate(
    con,
    source: str,
    scope: str,
    mbid: str,
    genre: str,
    styles: str,
) -> int:
    rows = con.execute(
        '''
        SELECT
            id,
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
        ''',
        (source,),
    ).fetchall()
    ids = []
    for row in rows:
        if taxonomy.target_mbid_for_scope(row, scope) != mbid:
            continue
        row_genre = normalized_import_genre(con, row['raw_genre'])
        row_styles = '; '.join(split_values(row['raw_grouping'] or row['raw_style']))
        if genre and row_genre != genre:
            continue
        if styles and row_styles != styles:
            continue
        ids.append(row['id'])
    if not ids:
        return 0
    con.executemany('DELETE FROM library_tag_import WHERE id = ?', [(item,) for item in ids])
    con.commit()
    return len(ids)


def add_target_options(options: list[tuple[str, str, str]], scope: str, label: str, value: object) -> None:
    for mbid in split_mbid_values(str(value or '')):
        options.append((scope, label, mbid))


def import_id_block(row: dict, selected_scope: str) -> str:
    items = []
    if selected_scope == 'artist' and row.get('mbid'):
        items.append(('artist', 'Artist Decision Target', row.get('mbid')))
    else:
        items.extend(
            (
                ('album_artist', 'Album Artist', row.get('album_artist_mbid')),
                ('release_artist', 'Release Artist', row.get('release_artist_mbid')),
                ('track_artist', 'Track Artist', row.get('track_artist_mbid')),
            )
        )
    items.extend(
        (
            ('release_group', 'Release Group', row.get('release_group_mbid')),
            ('release', 'Album/Release', row.get('release_mbid')),
            ('recording', 'Track', row.get('recording_mbid')),
        )
    )
    parts = []
    for scope, label, value in items:
        if not value:
            continue
        selected = scope == selected_scope
        cls = 'id-line selected' if selected else 'id-line'
        marker = 'Using ' if selected else ''
        parts.append(f'<div class="{cls}"><span>{marker}{h(label)}</span>{mbid_display(str(value))}</div>')
    if not parts:
        return '<span class="muted">No matching MBID for selected scope</span>'
    return ''.join(parts)


def mbid_display(value: str) -> str:
    values = split_mbid_values(value)
    if len(values) <= 1:
        return f'<code>{h(value)}</code>'
    codes = ''.join(f'<code>{h(item)}</code>' for item in values)
    return f'<div class="mbid-list">{codes}<span class="hint">multiple artist IDs</span></div>'


def split_mbid_values(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []
    separator = ';' if ';' in value else '/' if '/' in value else ''
    if not separator:
        return [value]
    return [item.strip() for item in value.split(separator) if item.strip()]


def normalize_joined_values(value: str) -> str:
    return taxonomy.normalize_manual_list_text(value)


def normalized_import_genre(con, value: str | None) -> str:
    raw = taxonomy.normalize_manual_list_text(value)
    if not raw:
        return ''
    try:
        return taxonomy.normalize_genre_text(con, raw)
    except BaseException:
        return raw


def parse_import_target(value: str) -> tuple[str, str]:
    if '|' not in value:
        raise ValueError('Import target must include a scope and MBID.')
    scope, mbid = value.split('|', 1)
    return clean(scope), clean(mbid)


CSS = r'''
:root {
  color-scheme: light;
  --bg: #f6f7f8;
  --panel: #ffffff;
  --text: #1f2933;
  --muted: #64707d;
  --line: #d9dee5;
  --accent: #176b87;
  --accent-dark: #0f4f66;
  --danger: #a33131;
  --ok-bg: #e9f7ef;
  --err-bg: #fdecec;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Segoe UI", system-ui, sans-serif;
  font-size: 15px;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--line);
  background: var(--panel);
}
h1 { margin: 0; font-size: 20px; font-weight: 650; }
h2 { margin: 0 0 14px; font-size: 17px; }
nav { display: flex; gap: 8px; }
nav a, .button, button {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  color: var(--text);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 7px 12px;
  text-decoration: none;
  font: inherit;
}
nav a.active, .button.primary, button {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.secondary-button {
  background: #fff;
  border-color: var(--line);
  color: var(--text);
}
.danger-button {
  background: #fff;
  border-color: var(--danger);
  color: var(--danger);
}
button:hover, .button:hover, nav a:hover { border-color: var(--accent-dark); }
main { max-width: 1220px; margin: 0 auto; padding: 24px; }
section, .panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  margin-bottom: 18px;
}
.toolbar, .danger-form { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.danger-form { justify-content: flex-end; margin-top: -8px; }
.filter-check { align-self: end; margin-bottom: 8px; }
.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  background: transparent;
  border: 0;
  padding: 0;
}
.metric {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
}
.metric span { color: var(--muted); display: block; font-size: 13px; }
.metric strong { display: block; font-size: 28px; margin-top: 4px; }
.split { display: grid; grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); gap: 18px; background: transparent; border: 0; padding: 0; }
label { display: grid; gap: 6px; margin-bottom: 12px; font-weight: 600; }
.compact-label {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 10px;
}
input, select, textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--text);
  font: inherit;
  padding: 8px 10px;
}
textarea { resize: vertical; }
.check { display: flex; align-items: center; gap: 8px; }
.check input { width: auto; }
.actions, .row-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--line); padding: 9px 8px; text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 13px; font-weight: 650; }
code { font-family: Consolas, monospace; font-size: 13px; }
.import-list {
  display: grid;
  gap: 14px;
}
.import-card {
  border-bottom: 1px solid var(--line);
  display: grid;
  gap: 14px;
  padding: 0 0 16px;
}
.import-card:last-child { border-bottom: 0; padding-bottom: 0; }
.import-summary {
  align-items: start;
  display: grid;
  gap: 14px;
  grid-template-columns: 58px minmax(220px, 1fr) auto;
}
.track-count {
  color: var(--accent-dark);
  font-size: 22px;
  font-weight: 650;
  line-height: 1;
}
.track-count span {
  color: var(--muted);
  display: block;
  font-size: 11px;
  font-weight: 600;
  margin-top: 4px;
}
.approve-actions {
  align-items: center;
  display: flex;
  gap: 10px;
}
.import-fields {
  display: grid;
  gap: 14px;
  grid-template-columns: minmax(240px, 1.2fr) minmax(180px, .8fr) minmax(280px, 1.6fr);
}
.import-fields select,
.import-fields input {
  font-size: 13px;
}
.grouping-editor {
  margin-bottom: 0;
}
.grouping-editor textarea {
  min-height: 118px;
}
.mbid-list {
  display: grid;
  gap: 2px;
}
.id-line code {
  overflow-wrap: anywhere;
}
.link {
  background: transparent;
  border: 0;
  color: var(--danger);
  min-height: 0;
  padding: 0;
}
.badge {
  display: inline-block;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #f9fafb;
  font-size: 12px;
  font-weight: 650;
  padding: 3px 8px;
}
.hint {
  color: var(--muted);
  display: block;
  font-size: 12px;
  margin-top: 4px;
}
.muted { color: var(--muted); }
.id-line {
  display: grid;
  gap: 3px;
  margin-bottom: 8px;
}
.id-line span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 650;
}
.id-line.selected {
  border-left: 3px solid var(--accent);
  padding-left: 8px;
}
.id-line.selected span { color: var(--accent-dark); }
.alert { border-radius: 6px; margin-bottom: 18px; padding: 10px 12px; }
.alert.ok { background: var(--ok-bg); }
.alert.error { background: var(--err-bg); color: var(--danger); }
@media (max-width: 760px) {
  header { align-items: flex-start; flex-direction: column; }
  .split { grid-template-columns: 1fr; }
  .import-summary,
  .import-fields { grid-template-columns: 1fr; }
  .approve-actions { justify-content: flex-start; }
  table { display: block; overflow-x: auto; }
}
'''


def main() -> int:
    parser = argparse.ArgumentParser(description='Local web UI for Picard Genre DB')
    parser.add_argument('--db', default='taxonomy.db')
    parser.add_argument('--json', default='taxonomy.json')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8686)
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()

    global DB_PATH, JSON_PATH
    DB_PATH = args.db
    JSON_PATH = args.json

    port = first_available_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), AppHandler)
    url = f'http://{args.host}:{port}'
    print(f'Picard Genre DB running at {url}')
    print(f'Database: {Path(DB_PATH).resolve()}')
    print(f'Plugin JSON: {Path(JSON_PATH).resolve()}')

    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping server.')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
