# jmm subtitles

Download subtitles from OpenSubtitles.

## Overview

The subtitles command downloads subtitles for your media files using the OpenSubtitles API. It uses file hashing for accurate matching and supports multiple languages.

## Subcommands

| Command | Description |
|---------|-------------|
| `jmm subtitles download` | Download subtitles for files |
| `jmm subtitles status` | Show OpenSubtitles API status |

---

## jmm subtitles download

Download subtitles for media files.

### Usage

```bash
jmm subtitles download [PATH] [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `path` | No | File or directory to download subtitles for |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type`, `-t` | | Media type for library-wide: `tv`, `movies`, or `both` |
| `--language`, `-l` | from config | Subtitle languages (comma-separated) |
| `--overwrite`, `-o` | false | Overwrite existing subtitles |
| `--dry-run`, `-n` | false | Show what would be downloaded |

### Examples

```bash
# Download for single file
jmm subtitles download /path/to/movie.mkv

# Download for directory
jmm subtitles download /path/to/show/Season\ 01/

# Download for entire TV library
jmm subtitles download --type tv

# Download for all media
jmm subtitles download --type both

# Specify languages
jmm subtitles download /path/to/movie.mkv -l en,es,fr

# Preview without downloading
jmm subtitles download --type both --dry-run

# Force re-download
jmm subtitles download /path/to/movie.mkv --overwrite
```

---

## jmm subtitles status

Check OpenSubtitles API status and usage.

### Usage

```bash
jmm subtitles status
```

### Output

```
OpenSubtitles Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
API Key:      ✓ Configured
Status:       ✓ Connected
Languages:    en, es
Downloads:    45/200 today
Resets at:    00:00 UTC
```

---

## Language Codes

Common ISO 639-1 language codes:

| Code | Language |
|------|----------|
| en | English |
| es | Spanish |
| fr | French |
| de | German |
| pt | Portuguese |
| it | Italian |
| nl | Dutch |
| pl | Polish |
| ru | Russian |
| ja | Japanese |
| ko | Korean |
| zh | Chinese |

Set default languages in config:
```env
JMM_SUBTITLE_LANGUAGES=en,es,fr
```

---

## How Matching Works

OpenSubtitles uses multiple methods to find subtitles:

1. **File Hash** (most accurate)
   - Computes hash from video file
   - Matches exact release
   - Subtitles are synced

2. **IMDB ID**
   - Falls back to TMDb → IMDB lookup
   - May need manual sync

3. **Filename**
   - Last resort
   - Least accurate

---

## Output Naming

Subtitles are named to match your video file:

```
Movie (2024).mkv
Movie (2024).en.srt      # English
Movie (2024).es.srt      # Spanish
Movie (2024).fr.srt      # French
```

Media players (Plex, Kodi, VLC) auto-detect these sidecar subtitles.

---

## API Limits

### Free Tier
- **200 downloads per day** per user
- **5 downloads per second** rate limit
- Resets at midnight UTC

### Checking Usage

```bash
jmm subtitles status
```

Shows remaining downloads for the day.

### When Limit Reached

```
Error: Daily download limit reached (200/200)
Resets at: 00:00 UTC
```

Prioritize which files need subtitles or wait until tomorrow.

---

## Configuration

Settings in `~/.jackmediaman.env`:

```env
# Provider: "org" (default) or "com"
JMM_OPENSUBTITLES_PROVIDER=org

# Credentials (required)
JMM_OPENSUBTITLES_USERNAME=your_username
JMM_OPENSUBTITLES_PASSWORD=your_password

# API key (OpenSubtitles.com only)
JMM_OPENSUBTITLES_API_KEY=your_api_key

# Default languages
JMM_SUBTITLE_LANGUAGES=en,es
```

Setup guide: See [OpenSubtitles Setup](Setup-OpenSubtitles)

---

## Output Example

```
Downloading subtitles...

✓ The Matrix (1999).mkv
  Downloaded: The Matrix (1999).en.srt

✓ Breaking Bad - S01E01.mkv
  Downloaded: Breaking Bad - S01E01.en.srt
  Downloaded: Breaking Bad - S01E01.es.srt

✗ Some.Obscure.Movie.2024.mkv
  No subtitles found for language: en

Summary: 3/4 files successful
```

---

## Troubleshooting

### No Subtitles Found

Possible causes:
1. Subtitles don't exist on OpenSubtitles
2. File hash doesn't match any known release
3. Language not available

Solutions:
- Try additional languages: `-l en,es,pt`
- Search manually on [opensubtitles.com](https://www.opensubtitles.com/)
- Try a different release of the video

### Authentication Failed

```
Error: 401 Unauthorized
```

- Verify API key is correct
- Check key hasn't been revoked
- Run `jmm setup opensubtitles`

### Wrong Subtitles (Out of Sync)

This is rare with hash-based matching, but can happen with:
- Re-encoded files
- Modified releases

Solutions:
- Delete and re-download
- Search manually for alternate subtitles
- Use subtitle sync tools

---

## In Processing Pipeline

Subtitles are automatically downloaded during `jmm process`:

```bash
# Include subtitles (default)
jmm process run /path/to/torrent

# Skip subtitle download
jmm process run /path/to/torrent --no-subtitles
```

---

## Related Pages

- [Setup OpenSubtitles](Setup-OpenSubtitles) - API key setup
- [Configuration](Configuration) - All settings
- [Commands: process](Commands-Process) - Automatic subtitles
