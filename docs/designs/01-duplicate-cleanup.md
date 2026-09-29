# JackMediaMan - Duplicate Cleanup Feature Design

## Overview

The duplicate cleanup feature scans TV Shows and Movies folders to find duplicate files, keeping the highest quality version while protecting files that are actively seeding.

## User Flow

### Interactive Mode
```bash
jackmediaman duplicates
```

Shows Rich interactive menu to choose:
1. What to scan (TV/Movies/Both)
2. Movie matching strategy
3. Protection method
4. Edition handling

### CLI Mode
```bash
# Scan and show duplicates (dry-run)
jackmediaman duplicates scan --type movies --matcher tmdb --protector both

# Execute cleanup
jackmediaman duplicates clean --execute --auto
```

## Architecture

### Models

```
MediaItem (base)
├── Movie
│   ├── title: str
│   ├── year: int
│   └── tmdb_id: Optional[int]
└── Episode
    ├── series_name: str
    ├── season: int
    └── episode: int

Quality
├── resolution: Resolution (4K, 1080p, 720p, SD)
├── source: str (BluRay, WEB-DL, HDTV)
├── codec: str (x265, x264)
└── score() -> int

DuplicateGroup
├── items: List[MediaItem]
├── best_quality() -> MediaItem
├── protected_items() -> List[MediaItem]
└── removable() -> List[MediaItem]
```

### Scanners

**TVScanner**: Walks `TV Shows/ShowName/Season X/` structure
**MovieScanner**: Walks `Movies/MovieName (Year)/` structure

Both parse quality information from filenames.

### Matchers

**TV Matcher**: Groups by show + season + episode number

**Movie Matchers** (user chooses):
1. **TitleYearMatcher**: Parse folder name, normalize, compare
2. **FuzzyMatcher**: Levenshtein distance for variations
3. **TMDbMatcher**: API lookup for canonical movie ID

### Protectors

**SymlinkProtector**: Checks if file is symlink to torrent directory
**DelugeProtector**: Queries Deluge daemon for seeding status

### Quality Scoring

```python
score = resolution_score + source_score + codec_score + hdr_bonus

Resolution scores:
- 4K/2160p: 4000
- 1080p: 3000
- 720p: 2000
- SD: 1000

Source scores:
- BluRay: 60
- WEB-DL: 40
- HDTV: 20

Codec scores:
- x265: 12
- x264: 10

HDR bonus: +10
```

## Output Display

```
┌─ Duplicate Groups Found ───────────────────────────────────────────┐
│ Media           │ File                          │ Quality │ Action │
├─────────────────┼───────────────────────────────┼─────────┼────────┤
│ Dune (2021)     │ Dune.2021.2160p.BluRay.mkv   │ 4K BR   │ KEEP   │
│                 │ Dune.2021.1080p.WEB-DL.mkv   │ 1080p   │ REMOVE │
└────────────────────────────────────────────────────────────────────┘

Summary: 5 groups, 8 removable files (23.4 GB)
```

## Cleanup Actions

1. **Dry-run** (default): Display only, no changes
2. **Execute**: Move to trash with timestamp prefix
3. **Interactive**: Prompt for each group

Trash location: `~/.jackmediaman/trash/YYYYMMDD_HHMMSS_filename`
