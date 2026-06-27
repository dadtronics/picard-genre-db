"""Tests for the pure text-normalization and genre-resolution helpers."""
from __future__ import annotations

import pytest

import manage_taxonomy as taxonomy


def test_sanitize_value_collapses_whitespace():
    assert taxonomy.sanitize_value('  Acid   Jazz \n') == 'Acid Jazz'


def test_sanitize_value_none_is_empty():
    assert taxonomy.sanitize_value(None) == ''


def test_split_semicolon_values_drops_blanks_and_trims():
    assert taxonomy.split_semicolon_values('House ; ; Techno;') == ['House', 'Techno']


def test_split_semicolon_values_none():
    assert taxonomy.split_semicolon_values(None) == []


def test_normalize_manual_list_text_converts_separators():
    # Commas and newlines/tabs all become the canonical semicolon separator.
    assert taxonomy.normalize_manual_list_text('Electronic, Jazz\nRap') == 'Electronic; Jazz; Rap'


def test_normalize_term_key_folds_punctuation_and_ampersand():
    assert taxonomy.normalize_term_key('Drum & Bass') == 'drum and bass'
    assert taxonomy.normalize_term_key('Hip-Hop/Rap') == 'hip hop rap'


def test_resolve_genre_name_canonical_is_case_insensitive(con):
    assert taxonomy.resolve_genre_name(con, 'electronic') == 'Electronic'


def test_resolve_genre_name_via_alias_mapping(con):
    assert taxonomy.resolve_genre_name(con, 'EDM') == 'Electronic'


def test_resolve_genre_name_via_builtin_alias(con):
    assert taxonomy.resolve_genre_name(con, 'hip-hop') == 'Rap'


def test_resolve_genre_name_unknown_raises(con):
    with pytest.raises(taxonomy.TaxonomyError):
        taxonomy.resolve_genre_name(con, 'Definitely Not A Genre')


def test_normalize_genres_dedups_and_keeps_primary(con):
    genre_id, primary, text = taxonomy.normalize_genres(con, 'Electronic; electronic; Jazz')
    assert primary == 'Electronic'
    assert text == 'Electronic; Jazz'
    assert genre_id == taxonomy.get_genre_id(con, 'Electronic')


def test_normalize_genres_requires_at_least_one(con):
    with pytest.raises(taxonomy.TaxonomyError):
        taxonomy.normalize_genres(con, '   ')


def test_get_style_id_unknown_raises(con):
    with pytest.raises(taxonomy.TaxonomyError):
        taxonomy.get_style_id(con, 'Nonexistent Style')
