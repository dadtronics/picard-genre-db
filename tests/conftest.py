"""Shared pytest fixtures: an in-memory taxonomy DB seeded with vocabulary."""
from __future__ import annotations

import pytest

import manage_taxonomy as taxonomy


@pytest.fixture()
def con():
    """An in-memory SQLite connection with schema and starter vocabulary."""
    connection = taxonomy.connect(':memory:')
    taxonomy.ensure_schema(connection)

    for genre in ('Electronic', 'Rap', 'Pop/Rock', 'Jazz'):
        taxonomy.add_genre(connection, genre)
    taxonomy.add_style(connection, 'Electronic', 'House')
    taxonomy.add_style(connection, 'Electronic', 'Techno')
    taxonomy.add_style(connection, 'Jazz', 'Acid Jazz')
    # A user-defined alias mapping (distinct from the built-in aliases).
    taxonomy.add_alias(connection, 'test', 'EDM', 'Electronic', None, None, 1.0)

    try:
        yield connection
    finally:
        connection.close()
