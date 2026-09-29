# jmm process

Process completed torrent downloads through the media pipeline.

## Overview

The process command is the heart of JackMediaMan's automation. It takes a torrent download and:
1. Extracts archives (RAR, ZIP, 7z)
2. Identifies media type (movie vs TV)
3. Organizes into library structure
4. Creates links/copies
5. Downloads subtitles
6. Downloads artwork

## Usage

```bash
jmm process run <path> [OPTIONS]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `path` | Yes | Path to completed torrent (file or directory) |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--action`, `-a` | `symlink` | File action mode |
| `--dry-run`, `-n` | false | Preview without making changes |
| `--no-extract` | false | Skip archive extraction |
| `--no-tmdb` | false | Skip TMDb metadata lookup |
| `--no-subtitles` | false | Skip subtitle download |
| `--no-artwork` | false | Skip artwork download |

---

## Action Modes

| Mode | What Happens | Best For |
|------|--------------|----------|
| `symlink` | Creates symlink in library pointing to source | Keep seeding, minimal space |
| `keeplink` | Moves to library, leaves symlink at source | Keep seeding, organized library |
| `hardlink` | Creates hard link (same inode) | Same filesystem, keep seeding |
| `copy` | Copies file (2x disk space) | Different filesystem, keep seeding |
| `move` | Moves file to library | Done seeding |

### Which Action to Choose?

**Want to keep seeding?**
- Same filesystem: `hardlink` or `keeplink`
- Different filesystem: `symlink` or `copy`

**Done seeding?**
- Use `move`

**Most common:**
- `keeplink` - Best of both worlds

---

## Examples

### Basic Processing

```bash
# Preview what will happen
jmm process run /downloads/Movie.2024.1080p.BluRay --dry-run

# Process with symlinks (default)
jmm process run /downloads/Movie.2024.1080p.BluRay

# Process with keeplink (move + symlink for seeding)
jmm process run /downloads/Movie.2024.1080p.BluRay --action keeplink
```

### Movies vs TV Shows

```bash
# Movie
jmm process run /downloads/The.Matrix.1999.1080p.BluRay
# Result: /media/Movies/The Matrix (1999)/The Matrix (1999) [1080p].mkv

# TV Episode
jmm process run /downloads/Breaking.Bad.S01E01.720p.HDTV
# Result: /media/TV Shows/Breaking Bad/Season 01/Breaking Bad - S01E01 [720p].mkv
```

### With Archives

```bash
# Process torrent with RAR files
jmm process run /downloads/Movie.2024.1080p.BluRay-GROUP
# Automatically extracts RAR, processes video
```

### Skip Options

```bash
# Skip everything except linking
jmm process run /path --no-extract --no-tmdb --no-subtitles --no-artwork

# Just extract and link, no metadata
jmm process run /path --no-tmdb --no-subtitles --no-artwork
```

---

## Pipeline Stages

The process command runs through 6 stages:

### 1. Extractor
- Finds archives (.rar, .zip, .7z)
- Extracts to temporary directory
- Handles multi-part and nested archives
- Filters out sample files

### 2. Identifier
- Detects media type (TV vs Movie)
- Parses metadata from filename
- Optionally queries TMDb

### 3. Organizer
- Calculates destination paths
- Creates standard naming

### 4. Linker
- Executes file operations
- Creates directories
- Handles conflicts

### 5. Subtitles
- Downloads from OpenSubtitles
- Matches by file hash
- Multiple language support

### 6. Artwork
- Downloads posters from TMDb
- Movie and TV show posters

See [Pipeline](Pipeline) for detailed stage information.

---

## Output Format

### Movie Result

```
Processing: /downloads/The.Matrix.1999.1080p.BluRay

Stage Results:
┌──────────┬─────────┬───────────────────────────────────┐
│ Stage    │ Status  │ Details                           │
├──────────┼─────────┼───────────────────────────────────┤
│ Extract  │ ✓ ok    │ No archives found                 │
│ Identify │ ✓ ok    │ Movie: The Matrix (1999)          │
│ Organize │ ✓ ok    │ → Movies/The Matrix (1999)/       │
│ Linker   │ ✓ ok    │ keeplink: 1 file                  │
│ Subtitle │ ✓ ok    │ Downloaded: en                    │
│ Artwork  │ ✓ ok    │ Downloaded: poster.jpg            │
└──────────┴─────────┴───────────────────────────────────┘

SUCCESS: 1 file processed
```

### Dry Run Output

```
DRY RUN - No changes made

File Mappings:
  The.Matrix.1999.1080p.BluRay.mkv
    → /media/Movies/The Matrix (1999)/The Matrix (1999) [1080p].mkv
```

---

## Configuration

Related settings in `~/.jackmediaman.env`:

```env
# Default action (overridden by --action)
JMM_PROCESS_DEFAULT_ACTION=keeplink

# Extraction directory (uses temp if not set)
JMM_PROCESS_EXTRACT_DIR=/tmp/jmm-extract

# Delete archives after extraction
JMM_PROCESS_CLEANUP_ARCHIVES=false
```

---

## Automation

### Deluge Execute Plugin

Configure Deluge to run `jmm process` on torrent completion:

```bash
#!/bin/bash
# /home/user/bin/jmm-hook.sh
jmm process run "$3/$2" --action keeplink
```

See [Deluge Setup](Setup-Deluge) for full instructions.

### Manual Batch Processing

```bash
# Process all torrents in directory
for dir in /downloads/completed/*/; do
    jmm process run "$dir" --action keeplink
done
```

---

## Troubleshooting

### Archive Extraction Fails

Install extraction tools:
```bash
# Ubuntu/Debian
sudo apt install unrar p7zip-full

# Or install Python packages
pip install rarfile py7zr
```

### Wrong Media Type Detected

If a movie is detected as TV (or vice versa):
1. The filename may contain "S01" or similar
2. Rename the file to remove TV-like patterns
3. Use `--no-tmdb` if TMDb is returning wrong results

### Destination Exists

Currently, process fails if the destination file exists. Workaround:
- Delete the existing file
- Rename the existing file
- Process with a different action mode

---

## Related Pages

- [Pipeline](Pipeline) - Detailed stage documentation
- [Setup Deluge](Setup-Deluge) - Automation setup
- [Configuration](Configuration) - Process settings
- [Commands: subtitles](Commands-Subtitles) - Subtitle options
- [Commands: artwork](Commands-Artwork) - Artwork options
