# Concepts

## Two Different Things

The database stores two kinds of information.

Canonical values are the allowed vocabulary:

```text
Electronic
Pop/Rock
Reggae
House
Techno
Club/Dance
```

Decisions attach those values to MusicBrainz IDs:

```text
release-group MBID abc123 -> genre Electronic -> grouping Electro-Techno; Techno; Club/Dance
```

The canonical tables answer: "What values am I allowed to use?"

The decision tables answer: "What should Picard write for this artist, album, or track?"

## Scope

Scope means how broadly a decision applies.

Use `artist` when the source is an artist page or the style should apply to most music by that artist.

Use `release_group` when the source is an album/single/EP page. This is the normal "album default" scope.

Use `recording` when one track needs to be different.

Ignore `release` for most day-to-day use. It is for one exact CD/release/pressing.

The useful mental model is:

```text
Artist default
Album default
Track override
```

The plugin lookup order is:

```text
recording -> release -> release_group -> artist -> alias mapping
```

So a track decision beats an album decision, and an album decision beats an artist default.

## Multi-Genre Values

Use semicolons:

```text
Pop/Rock; Reggae
```

The first genre is stored as the primary genre for DB indexing. Picard still writes the full semicolon-separated value.

When new styles are auto-created by a decision command, they are created under the first genre.

## Tags Written By The Plugin

The plugin writes:

```text
genre
style
grouping
```

`grouping` is the important style/subgenre tag for your current workflow.

Alias mappings only write these fields if Picard's New Value metadata is empty.

Explicit DB decisions are authoritative by default. If a recording, release,
release-group, or artist decision exists, it can replace Picard/MusicBrainz
values such as `Hip-Hop` with your canonical value such as `Rap`.
