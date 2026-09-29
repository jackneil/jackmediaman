# Processing Pipeline

The `jmm process` command uses a pipeline architecture to process torrent downloads. Each stage handles a specific task and passes data to the next stage.

## Pipeline Overview

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Extractor  │ -> │  Identifier  │ -> │  Organizer   │
└──────────────┘    └──────────────┘    └──────────────┘
                           │
                           v
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Artwork    │ <- │  Subtitles   │ <- │    Linker    │
└──────────────┘    └──────────────┘    └──────────────┘
```

## Stage 1: Extractor

**Purpose:** Extract archives from torrent downloads.

**What it does:**
- Finds archives in the source path (RAR, ZIP, 7z, tar)
- Handles multi-part RAR files (only extracts from .rar or .part01.rar)
- Extracts nested archives (up to 3 levels deep)
- Filters out sample/proof files
- Identifies video files for next stage

**Supported formats:**
| Format | Method |
|--------|--------|
| .rar | unrar, 7z, or rarfile package |
| .zip | Python zipfile module |
| .7z | 7z command or py7zr package |
| .tar, .tar.gz, .tgz | Python tarfile module |

**Skips automatically:**
- Sample files (containing "sample" in name)
- Proof files (containing "proof" in name)
- Non-video files (.nfo, .txt, .sfv, .par2)

**Skip this stage:**
```bash
jmm process run /path --no-extract
```

---

## Stage 2: Identifier

**Purpose:** Detect media type and extract metadata.

**What it does:**
1. Parses filename for TV patterns (S01E01, 1x01, etc.)
2. If TV pattern found: extracts show name, season, episode(s)
3. If no TV pattern: treats as movie, extracts title and year
4. Optionally queries TMDb for canonical metadata
5. Parses quality info from filename

**TV detection patterns:**
- `S01E01` - Standard format
- `S01E01E02E03` - Multi-episode
- `S01E01-E05` - Episode range
- `1x01` - Alternate format
- `Season 1 Episode 1` - Verbose format

**Title cleaning:**
- Replaces dots/underscores with spaces
- Removes quality tags (1080p, BluRay, x264, etc.)
- Strips release group suffix

**TMDb lookup (optional):**
- Searches for movie/show by title
- Gets canonical title and year
- Increases identification confidence

**Skip TMDb:**
```bash
jmm process run /path --no-tmdb
```

---

## Stage 3: Organizer

**Purpose:** Calculate destination paths for each file.

**Naming conventions:**

**Movies:**
```
{movies_dir}/Movie Name (Year)/Movie Name (Year) [Resolution].ext

Example:
/media/Movies/The Matrix (1999)/The Matrix (1999) [1080p].mkv
```

**TV Episodes:**
```
{tv_dir}/Show Name/Season XX/Show Name - S01E01 [Resolution].ext

Example:
/media/TV Shows/Breaking Bad/Season 01/Breaking Bad - S01E01 [1080p].mkv
```

**Multi-episode files:**
```
Show Name - S01E01-E03 [1080p].mkv
```

**Resolution tags:**
- `[2160p]` for 4K
- `[1080p]` for Full HD
- `[720p]` for HD
- No tag for SD

---

## Stage 4: Linker

**Purpose:** Execute file operations.

**Action modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `move` | Move file to library | Stop seeding |
| `copy` | Copy file | Keep seeding (2x space) |
| `hardlink` | Create hard link | Same filesystem only |
| `symlink` | Create symbolic link | Default, keep seeding |
| `keeplink` | Move + leave symlink at source | Keep seeding, organized library |

**File operations:**
1. Creates destination directories
2. Checks if destination exists (fails if it does)
3. Executes operation based on action mode
4. Records operation for potential rollback

**Conflict behavior:**
Currently skips if destination exists. Future versions will support:
- Override existing
- Auto-compare quality
- Rename with suffix

---

## Stage 5: Subtitles

**Purpose:** Download subtitles for processed media.

**What it does:**
- Downloads from OpenSubtitles API
- Uses file hash for accurate matching
- Supports multiple languages
- Names subtitle files to match video

**Requirements:**
- OpenSubtitles API key configured
- Network access

**Skip this stage:**
```bash
jmm process run /path --no-subtitles
```

---

## Stage 6: Artwork

**Purpose:** Download poster artwork.

**What it does:**
- Downloads from TMDb
- Movie posters: `poster.jpg` in movie folder
- TV posters: `poster.jpg` in show folder
- Season posters: `season01.jpg` etc.

**Requirements:**
- TMDb API key configured
- Network access

**Skip this stage:**
```bash
jmm process run /path --no-artwork
```

---

## Pipeline Context

The pipeline passes a `ProcessContext` object through each stage:

```python
context = ProcessContext(
    source_path=Path("/downloads/Movie.2024.1080p"),
    action=ActionMode.KEEPLINK,
    dry_run=False,
)
```

**Context fields populated by stages:**

| Stage | Populates |
|-------|-----------|
| Extractor | `extracted_files`, `video_files`, `work_dir` |
| Identifier | `identified_media` |
| Organizer | `file_mappings` |
| Linker | `completed_operations` |
| Subtitles | (modifies files on disk) |
| Artwork | (modifies files on disk) |

---

## Rollback Support

Each stage supports rollback in case of failure:

- **Extractor:** Deletes temporary extraction directory
- **Identifier:** No rollback needed (read-only)
- **Organizer:** No rollback needed (path calculation only)
- **Linker:** Reverses file operations (moves back, deletes copies/links)
- **Subtitles:** Deletes downloaded subtitle files
- **Artwork:** Deletes downloaded artwork files

Rollback is automatic when a stage fails.

---

## Dry Run Mode

Preview what would happen without making changes:

```bash
jmm process run /path --dry-run
```

In dry run mode:
- Extractor runs normally (to find video files)
- Identifier runs normally
- Organizer runs normally
- Linker records operations but doesn't execute
- Subtitles skipped
- Artwork skipped

Output shows all planned operations.

---

## Stage Results

Each stage returns a result status:

| Status | Meaning |
|--------|---------|
| `success` | All items processed successfully |
| `partial` | Some items processed, some failed |
| `failed` | No items could be processed |
| `skipped` | Stage skipped (disabled or not applicable) |

The pipeline continues on `success` or `partial`, stops on `failed`.

---

## Example Flow

Processing `The.Matrix.1999.1080p.BluRay.x264-GROUP`:

```
1. Extractor
   - No archives found
   - Found: The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv
   - Status: success

2. Identifier
   - No TV pattern found
   - Parsed: title="The Matrix", year=1999
   - TMDb: confirmed, id=603
   - Status: success

3. Organizer
   - Destination: /media/Movies/The Matrix (1999)/The Matrix (1999) [1080p].mkv
   - Directories to create: [/media/Movies/The Matrix (1999)]
   - Status: success

4. Linker (action=keeplink)
   - Moved file to destination
   - Created symlink at source
   - Status: success

5. Subtitles
   - Downloaded: The Matrix (1999).en.srt
   - Status: success

6. Artwork
   - Downloaded: poster.jpg
   - Status: success

Pipeline complete: 1 file processed
```

---

## Related Pages

- [Commands: process](Commands-Process) - Process command reference
- [Configuration](Configuration) - Pipeline-related settings
- [Quality Scoring](Quality-Scoring) - How quality is determined
