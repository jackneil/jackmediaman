# jmm rename

Rename media files to a standardized format.

## Overview

The rename command scans your media library and renames files to a consistent format compatible with Plex, Kodi, and other media servers.

## Subcommands

| Command | Description |
|---------|-------------|
| `jmm rename preview` | Preview renames without making changes |
| `jmm rename execute` | Execute file renames |
| `jmm rename` | Interactive mode |

---

## jmm rename preview

Preview what files would be renamed.

### Usage

```bash
jmm rename preview [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type`, `-t` | `both` | Media type: `tv`, `movies`, or `both` |

### Examples

```bash
# Preview all renames
jmm rename preview

# Preview TV shows only
jmm rename preview --type tv

# Preview movies only
jmm rename preview --type movies
```

---

## jmm rename execute

Execute the renames.

### Usage

```bash
jmm rename execute [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type`, `-t` | `both` | Media type: `tv`, `movies`, or `both` |
| `--yes`, `-y` | false | Skip confirmation prompt |

### Examples

```bash
# Execute with confirmation
jmm rename execute

# Execute without confirmation
jmm rename execute --yes

# Execute TV shows only
jmm rename execute --type tv --yes
```

---

## Naming Formats

### Movies

**Format:**
```
Movie Name (Year) [Resolution].ext
```

**Examples:**
```
Before: The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv
After:  The Matrix (1999) [1080p].mkv

Before: inception.2010.4k.hdr.mkv
After:  Inception (2010) [2160p].mkv
```

### TV Episodes

**Format:**
```
Show Name - S##E## [Resolution].ext
```

**Examples:**
```
Before: Breaking.Bad.S01E01.Pilot.720p.HDTV.mkv
After:  Breaking Bad - S01E01 [720p].mkv

Before: game.of.thrones.1x01.winter.is.coming.1080p.mkv
After:  Game of Thrones - S01E01 [1080p].mkv
```

### Multi-Episode Files

```
Before: Show.S01E01E02E03.mkv
After:  Show - S01E01-E03.mkv
```

---

## Resolution Tags

Resolution is detected from filename or FFprobe:

| Tag | Resolution |
|-----|------------|
| `[2160p]` | 4K / UHD |
| `[1080p]` | Full HD |
| `[720p]` | HD |
| (none) | SD / 480p |

---

## What Gets Cleaned

The rename process removes:
- Quality tags (1080p, BluRay, WEB-DL, etc.)
- Codec info (x264, x265, HEVC)
- Release groups (-GROUP, -RARBG, etc.)
- Scene formatting (dots, underscores)
- Audio tags (AAC, DTS, 5.1)

---

## TMDb Integration

For TV episodes, TMDb can provide:
- Canonical show names
- Episode titles (optional)

**With TMDb:**
```
Breaking Bad - S01E01 - Pilot [1080p].mkv
```

**Without TMDb:**
```
Breaking Bad - S01E01 [1080p].mkv
```

Configure TMDb: `jmm setup tmdb`

---

## FFprobe Integration

When enabled, FFprobe provides accurate resolution detection:
- Reads actual video dimensions
- Detects 4K upscales
- Handles non-standard resolutions

Configure: `JMM_FFPROBE_ENABLED=true`

Without FFprobe, resolution is parsed from filename only.

---

## Interactive Mode

Run `jmm rename` without subcommand for guided experience:

```bash
jmm rename
```

Or select "Rename Media" from the main menu (`jmm`).

---

## Output Example

```
Rename Preview (TV Shows)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breaking Bad/Season 01/
  Breaking.Bad.S01E01.720p.HDTV.mkv
  → Breaking Bad - S01E01 [720p].mkv

  Breaking.Bad.S01E02.Cats.in.the.Bag.720p.mkv
  → Breaking Bad - S01E02 [720p].mkv

Game of Thrones/Season 01/
  game.of.thrones.1x01.winter.is.coming.1080p.bluray.mkv
  → Game of Thrones - S01E01 [1080p].mkv

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 3 files to rename
```

---

## Safety Features

- **Preview first:** Always run `preview` before `execute`
- **Confirmation:** Execute asks for confirmation (bypass with `--yes`)
- **No duplicates:** Won't create naming conflicts
- **Extension preserved:** Only renames, doesn't change format

---

## Troubleshooting

### Wrong Show Name

If the show name is parsed incorrectly:
1. The filename may be ambiguous
2. Configure TMDb for better matching: `jmm setup tmdb`

### Missing Resolution Tag

If resolution tag is missing:
1. Enable FFprobe: `JMM_FFPROBE_ENABLED=true`
2. Or add resolution to original filename

### Year Not Detected

For movies, year is extracted from:
- Parentheses: `Movie (2024)`
- Filename: `Movie.2024.1080p`

If year is missing, the movie may not be recognized correctly.

---

## Related Pages

- [Setup TMDb](Setup-TMDb) - For accurate metadata
- [Configuration](Configuration) - FFprobe settings
- [Quality Scoring](Quality-Scoring) - Resolution detection
