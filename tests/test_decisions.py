"""Tests for decision persistence, the scope hierarchy, and JSON export."""
from __future__ import annotations

import json

import pytest

import manage_taxonomy as taxonomy


def test_decide_release_group_round_trips(con):
    taxonomy.decide_release_group(
        con,
        'rg-123',
        'Electronic; Jazz',
        'House; Techno',
        notes='hello',
        locked=True,
        ensure_styles=True,
    )
    row = con.execute(
        'SELECT * FROM release_group_decision WHERE release_group_mbid = ?',
        ('rg-123',),
    ).fetchone()
    assert row['genres_text'] == 'Electronic; Jazz'
    assert row['styles_text'] == 'House; Techno'
    assert row['notes'] == 'hello'
    assert row['locked'] == 1
    assert row['normalized_genre_id'] == taxonomy.get_genre_id(con, 'Electronic')


def test_decision_upsert_replaces_existing(con):
    taxonomy.decide_artist(con, 'a-1', 'Electronic', 'House', None, False, True)
    taxonomy.decide_artist(con, 'a-1', 'Jazz', 'Acid Jazz', None, False, True)
    rows = con.execute('SELECT genres_text, styles_text FROM artist_decision').fetchall()
    assert len(rows) == 1
    assert rows[0]['genres_text'] == 'Jazz'
    assert rows[0]['styles_text'] == 'Acid Jazz'


def test_decision_creates_styles_when_ensure_styles(con):
    taxonomy.decide_release(con, 'r-1', 'Electronic', 'Brand New Style', None, False, True)
    # ensure_styles=True should have created the previously-unknown style.
    assert taxonomy.get_style_id(con, 'Brand New Style')


def test_decision_rejects_unknown_style_without_ensure(con):
    with pytest.raises(taxonomy.TaxonomyError):
        taxonomy.decide_release(con, 'r-2', 'Electronic', 'Unseen Style', None, False, False)


def test_export_plugin_json_includes_decisions_and_aliases(con, tmp_path):
    taxonomy.decide_recording(con, 'rec-1', 'Electronic', 'House', None, False, True)
    out = tmp_path / 'taxonomy.json'
    taxonomy.export_plugin_json(con, str(out))

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['recording_decisions']['rec-1']['genre'] == 'Electronic'
    assert data['recording_decisions']['rec-1']['styles'] == 'House'
    # The seeded alias should be exported, keyed case-folded.
    assert data['aliases']['edm']['genre'] == 'Electronic'
