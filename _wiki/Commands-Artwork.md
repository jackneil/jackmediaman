# jmm artwork

Download poster artwork from TMDb.

## Overview

The artwork command downloads high-quality poster images for your media library from The Movie Database (TMDb).

## Subcommands

| Command | Description |
|---------|-------------|
| `jmm artwork download` | Download poster artwork |
| `jmm artwork status` | Show artwork coverage statistics |

---

## jmm artwork download

Download poster artwork for media.

### Usage

```bash
jmm artwork download [PATH] [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `path` | No | Specific folder to download artwork for |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type`, `-t` | | Media type for library-wide: `tv`, `movies`, or `both` |
| `--refresh`, `-r` | false | Re-download even if poster exists |
| `--dry-run`, `-n` | false | Show what would be downloaded |

### Examples

```bash
# Download for specific movie folder
jmm artwork download "/media/Movies/The Matrix (1999)"

# Download for specific TV show
jmm artwork download "/media/TV Shows/Breaking Bad"

# Download missing artwork for movies
jmm artwork download --type movies

# Download for all media
jmm artwork download --type both

# Preview without downloading
jmm artwork download --type both --dry-run

# Force refresh existing posters
jmm artwork download --type both --refresh
```

---

## jmm artwork status

Show artwork coverage statistics.

### Usage

```bash
jmm artwork status
```

### Output

```
Artwork Coverage
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Movies:
  Total:    150
  With art: 142
  Missing:  8
  Coverage: 94.7%

TV Shows:
  Total:    45
  With art: 40
  Missing:  5
  Coverage: 88.9%

Missing artwork:
  Movies/Some Obscure Film (2020)
  Movies/Another Movie (2019)
  TV Shows/Some Show
  ...
```

---

## Artwork Types

### Movies

Downloads `poster.jpg` to the movie folder:

```
Movies/
└── The Matrix (1999)/
    ├── The Matrix (1999) [1080p].mkv
    └── poster.jpg
```

### TV Shows

Downloads show poster and season posters:

```
TV Shows/
└── Breaking Bad/
    ├── poster.jpg           # Show poster
    ├── season01.jpg         # Season 1 poster
    ├── season02.jpg         # Season 2 poster
    └── Season 01/
        └── Breaking Bad - S01E01.mkv
```

---

## Image Quality

TMDb provides multiple poster sizes. JackMediaMan downloads:
- **Original quality** when available
- **w500** as fallback (500px wide)

Typical poster dimensions: ~680x1000 pixels

---

## Configuration

Requires TMDb API key:

```env
JMM_TMDB_API_KEY=your_api_key_here
```

Get API key: See [TMDb Setup](Setup-TMDb)

---

## Output Example

```
Downloading artwork...

✓ The Matrix (1999)
  Downloaded: poster.jpg

✓ Breaking Bad
  Downloaded: poster.jpg
  Downloaded: season01.jpg
  Downloaded: season02.jpg
  Downloaded: season03.jpg
  Downloaded: season04.jpg
  Downloaded: season05.jpg

✗ Some Obscure Movie (2020)
  Not found on TMDb

Summary: 6 posters downloaded, 1 failed
```

---

## Troubleshooting

### Not Found on TMDb

If artwork can't be found:
1. The title may not match TMDb exactly
2. The movie/show may not be on TMDb
3. Year might be different

Solutions:
- Check the exact title on [themoviedb.org](https://www.themoviedb.org/)
- Rename the folder to match TMDb
- Download manually

### Rate Limited

TMDb allows 40 requests per 10 seconds. If you hit this:
- JackMediaMan auto-throttles
- Wait and retry
- Process in smaller batches

### Wrong Poster

If the wrong poster is downloaded:
1. Multiple movies/shows have similar titles
2. Year disambiguation failed

Solutions:
- Ensure year is in folder name: `Movie (2024)`
- Delete wrong poster and re-download with `--refresh`
- Download correct poster manually

---

## In Processing Pipeline

Artwork is automatically downloaded during `jmm process`:

```bash
# Include artwork (default)
jmm process run /path/to/torrent

# Skip artwork download
jmm process run /path/to/torrent --no-artwork
```

---

## Media Server Integration

Downloaded posters are automatically used by:

- **Plex** - Recognizes `poster.jpg` in folders
- **Kodi** - Uses local artwork
- **Jellyfin** - Reads local images
- **Emby** - Supports folder images

---

## Related Pages

- [Setup TMDb](Setup-TMDb) - API key setup
- [Configuration](Configuration) - TMDb settings
- [Commands: process](Commands-Process) - Automatic artwork
