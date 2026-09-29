# Quality Scoring

JackMediaMan uses a quality scoring system to determine which file to keep when duplicates are found. Higher scores indicate better quality.

## How It Works

When multiple copies of the same movie or episode exist, JackMediaMan:

1. Calculates a quality score for each file
2. Ranks files by score (highest = best)
3. Keeps the highest-scored file
4. Marks lower-scored files as duplicates for removal

## Score Components

Quality scores are calculated from multiple factors:

### Resolution (Base Score)

| Resolution | Score | Detection |
|------------|-------|-----------|
| 4K / 2160p | 4000 | Filename or FFprobe |
| 1080p | 3000 | Filename or FFprobe |
| 720p | 2000 | Filename or FFprobe |
| SD / 480p | 1000 | Filename or FFprobe |

Resolution is the primary quality indicator and provides the base score.

### Source Quality (Bonus)

| Source | Score | Examples |
|--------|-------|----------|
| BluRay | +60 | BluRay, BDRip, BRRip |
| WEB-DL | +40 | WEB-DL, WEBDL, WEBRip |
| HDTV | +25 | HDTV, HDRip |
| DVDRip | +15 | DVDRip, DVD |
| CAM/TS | +0 | CAM, HDCAM, Telesync |

BluRay and WEB-DL releases are preferred over broadcast captures.

### Codec (Bonus)

| Codec | Score | Notes |
|-------|-------|-------|
| x265 / HEVC | +12 | Better compression, same quality |
| x264 / AVC | +10 | Standard codec |
| Other | +0 | XviD, DivX, etc. |

Modern codecs are slightly preferred for their efficiency.

### HDR (Bonus)

| Feature | Score |
|---------|-------|
| HDR | +20 |
| HDR10+ | +20 |
| Dolby Vision | +20 |

High Dynamic Range content gets a bonus.

---

## Score Examples

### Example 1: Same Movie, Different Qualities

```
Movie (2024).2160p.BluRay.x265.HDR.mkv
  Resolution: 4000 (4K)
  Source:     +60  (BluRay)
  Codec:      +12  (x265)
  HDR:        +20  (HDR)
  TOTAL:      4092 ← KEEP

Movie (2024).1080p.WEB-DL.x264.mkv
  Resolution: 3000 (1080p)
  Source:     +40  (WEB-DL)
  Codec:      +10  (x264)
  HDR:        +0
  TOTAL:      3050 ← Remove

Movie (2024).720p.HDTV.mkv
  Resolution: 2000 (720p)
  Source:     +25  (HDTV)
  Codec:      +0
  HDR:        +0
  TOTAL:      2025 ← Remove
```

### Example 2: Same Resolution, Different Sources

```
Movie (2024).1080p.BluRay.x265.mkv
  Resolution: 3000
  Source:     +60  (BluRay)
  Codec:      +12  (x265)
  TOTAL:      3072 ← KEEP

Movie (2024).1080p.WEB-DL.x264.mkv
  Resolution: 3000
  Source:     +40  (WEB-DL)
  Codec:      +10  (x264)
  TOTAL:      3050 ← Remove
```

### Example 3: TV Episodes

```
Show.S01E01.1080p.BluRay.x264.mkv
  Resolution: 3000
  Source:     +60  (BluRay)
  Codec:      +10  (x264)
  TOTAL:      3070 ← KEEP

Show.S01E01.720p.HDTV.mkv
  Resolution: 2000
  Source:     +25  (HDTV)
  Codec:      +0
  TOTAL:      2025 ← Remove
```

---

## Quality Detection Methods

### Filename Parsing

JackMediaMan extracts quality info from filenames using patterns:

```
Movie.2024.2160p.BluRay.x265.HDR-GROUP.mkv
       ↑     ↑     ↑    ↑
    Year  Res  Source Codec
```

### FFprobe Analysis

When enabled (`JMM_FFPROBE_ENABLED=true`), FFprobe provides:

- **Actual resolution** from video stream metadata
- **Codec identification** from stream info
- **HDR detection** from color transfer characteristics

FFprobe is more accurate than filename parsing, especially for:
- Re-encoded files with misleading names
- Files with non-standard naming
- Verifying claimed quality

---

## Handling Ties

When files have equal quality scores:

1. **File size** - Larger files often have better bitrate
2. **Original order** - First file found is preferred

In practice, ties are rare because the scoring system has enough granularity.

---

## Editions and Variants

### Default Behavior

By default, different editions are treated as duplicates:

```
Movie (2024).1080p.BluRay.mkv           ← Score: 3070
Movie (2024).Directors.Cut.1080p.mkv    ← Score: 3070 (duplicate)
Movie (2024).Extended.1080p.mkv         ← Score: 3070 (duplicate)
```

The highest-quality version is kept regardless of edition.

### Preserving Editions

To keep different editions as separate items:

```bash
jmm duplicates scan --editions-separate
```

This treats each edition as a unique item:
- "Movie (2024)" - Regular release
- "Movie (2024) - Director's Cut" - Separate item
- "Movie (2024) - Extended" - Separate item

---

## Customizing Quality Preferences

Currently, quality weights are hardcoded. Future versions may support:

- Custom resolution weights
- Source preference overrides
- Codec priority adjustments

For now, the defaults work well for most media libraries.

---

## Viewing Quality Scores

### In Duplicate Scan

```bash
jmm duplicates scan
```

Output shows quality scores:
```
┌─ The Matrix (1999) ──────────────────────────────┐
│ ✓ The.Matrix.1999.2160p.BluRay.x265.mkv  [4072]  │
│ ✗ The.Matrix.1999.1080p.WEB-DL.mkv       [3050]  │
│ ✗ The.Matrix.1999.720p.HDTV.mkv          [2025]  │
└──────────────────────────────────────────────────┘
```

### In Rename Preview

```bash
jmm rename preview
```

Shows detected quality in the output table.

---

## Related Pages

- [Commands: duplicates](Commands-Duplicates) - Duplicate detection
- [Configuration](Configuration) - FFprobe settings
- [Pipeline](Pipeline) - Quality detection in processing
