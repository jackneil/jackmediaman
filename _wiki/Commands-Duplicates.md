# jmm duplicates

Find and clean duplicate media files in your library.

## Overview

The duplicates command scans your TV and movie libraries for duplicate files, ranks them by quality, and helps you remove lower-quality copies while protecting files that are still seeding.

## Subcommands

| Command | Description |
|---------|-------------|
| `jmm duplicates scan` | Scan and display duplicates (dry-run) |
| `jmm duplicates clean` | Clean up duplicates by moving to trash |

---

## jmm duplicates scan

Scan for duplicates without making changes.

### Usage

```bash
jmm duplicates scan [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type`, `-t` | `both` | Media type: `tv`, `movies`, or `both` |
| `--matcher`, `-m` | `title_year` | Movie matching strategy |
| `--protector`, `-p` | `symlink` | Protection method for seeding files |
| `--editions-as-dupes` | (default) | Treat editions as duplicates |
| `--editions-separate` | | Keep editions as separate items |

### Matchers

| Matcher | Description | Requires |
|---------|-------------|----------|
| `title_year` | Parse title and year from filename (fast) | Nothing |
| `fuzzy` | Fuzzy string matching for variations | Nothing |
| `tmdb` | TMDb API lookup (most accurate) | TMDb API key |

### Protectors

| Protector | Description | Requires |
|-----------|-------------|----------|
| `symlink` | Protect files symlinked to torrent dir | Nothing |
| `deluge` | Query Deluge for seeding status | Deluge config |
| `both` | Use both methods | Deluge config |
| `none` | No protection | Nothing |

### Examples

```bash
# Scan all media with defaults
jmm duplicates scan

# Scan only movies with TMDb matching
jmm duplicates scan --type movies --matcher tmdb

# Scan with Deluge protection
jmm duplicates scan --protector deluge

# Keep different editions separate
jmm duplicates scan --editions-separate
```

---

## jmm duplicates clean

Clean up duplicates by moving them to trash.

### Usage

```bash
jmm duplicates clean [OPTIONS]
```

### Options

All options from `scan`, plus:

| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | (default) | Show what would be done |
| `--execute` | | Actually perform cleanup |
| `--interactive` | (default) | Ask before each removal |
| `--auto` | | Remove without asking |
| `--rename` | | Rename kept files to standard format |
| `--no-rename` | (default) | Don't rename kept files |

### Examples

```bash
# Preview cleanup
jmm duplicates clean

# Interactive cleanup (asks for each)
jmm duplicates clean --execute --interactive

# Automatic cleanup (no prompts)
jmm duplicates clean --execute --auto

# Cleanup and rename kept files
jmm duplicates clean --execute --auto --rename
```

---

## How It Works

### 1. Scanning

The scanner walks through your media directories and collects files:
- **TV:** Groups by show/season/episode
- **Movies:** Groups by title (and optionally year)

### 2. Matching

Files are grouped as duplicates using the selected matcher:
- **title_year:** Fast filename parsing
- **fuzzy:** Handles naming variations (80% similarity threshold)
- **tmdb:** API lookup for canonical matching

### 3. Quality Ranking

Within each duplicate group, files are ranked by [quality score](Quality-Scoring):
- Resolution (4K > 1080p > 720p > SD)
- Source (BluRay > WEB-DL > HDTV)
- Codec (x265 > x264)
- HDR bonus

### 4. Protection

Before marking for removal, files are checked:
- **Symlink protection:** Is the file a symlink to torrent directory?
- **Deluge protection:** Is the file being seeded?

Protected files are never removed.

### 5. Cleanup

Lower-quality duplicates are moved to the trash directory (`~/.jackmediaman/trash/`), not permanently deleted.

---

## Output Example

```
┌─ The Matrix (1999) ──────────────────────────────────────────┐
│ ✓ The.Matrix.1999.2160p.BluRay.x265.HDR.mkv     [4092] KEEP  │
│ ✗ The.Matrix.1999.1080p.WEB-DL.x264.mkv         [3050]       │
│ 🔗 The.Matrix.1999.720p.HDTV.mkv                [2025] SEED  │
└──────────────────────────────────────────────────────────────┘

Legend:
✓ = Keep (highest quality)
✗ = Remove (lower quality)
🔗 = Protected (seeding)
```

---

## Editions Handling

By default, different editions are treated as duplicates:
- "Movie (2024)" and "Movie (2024) Director's Cut" = duplicates

With `--editions-separate`:
- "Movie (2024)" = one item
- "Movie (2024) Director's Cut" = separate item

Detected editions:
- Director's Cut
- Extended
- Theatrical
- Unrated
- Special Edition
- Remastered

---

## Interactive Mode

Run `jmm` without arguments, then select "Find Duplicates" for a guided experience:

1. Choose media type (TV/Movies/Both)
2. Select matcher strategy
3. Choose protection method
4. Review duplicates
5. Confirm removals

---

## Tips

### Safe First Run

Always preview before executing:
```bash
jmm duplicates scan           # See what's found
jmm duplicates clean          # Preview cleanup
jmm duplicates clean --execute --interactive  # Confirm each
```

### Recovering Deleted Files

Files are moved to trash, not permanently deleted:
```bash
jmm trash list        # See what's in trash
jmm trash restore 1   # Restore by number
```

### Performance

For large libraries, `title_year` matcher is fastest. Use `tmdb` matcher when accuracy is more important than speed.

---

## Related Pages

- [Quality Scoring](Quality-Scoring) - How files are ranked
- [Setup Deluge](Setup-Deluge) - Enable Deluge protection
- [Commands: trash](Commands-Trash) - Managing trash
