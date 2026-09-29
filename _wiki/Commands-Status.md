# jmm status

Check configuration and service status.

## Overview

The status command shows the current configuration and connectivity status of JackMediaMan and its integrated services.

## Subcommands

| Command | Description |
|---------|-------------|
| `jmm status config` | Show configuration and service status |
| `jmm status deluge` | Check Deluge daemon connection |
| `jmm status tmdb` | Check TMDb API connection |
| `jmm status opensubtitles` | Check OpenSubtitles API status |
| `jmm status trash` | Show trash contents |
| `jmm status empty-trash` | Empty trash directory |

---

## jmm status config

Show all configuration settings and service status.

### Usage

```bash
jmm status config
```

### Output

```
JackMediaMan Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Media Paths:
  TV Shows:    /media/TV Shows     ✓ exists
  Movies:      /media/Movies       ✓ exists
  Torrents:    /downloads/completed ✓ exists
  Trash:       ~/.jackmediaman/trash ✓ exists

Services:
  TMDb:          ✓ Configured (key: abc...xyz)
  OpenSubtitles: ✗ Not configured
  Deluge:        ✓ Connected (127.0.0.1:58846)

Cache:
  Location:    ~/.jackmediaman/cache
  TTL:         24 hours
  FFprobe:     ✓ enabled (4 workers)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## jmm status deluge

Check Deluge daemon connection.

### Usage

```bash
jmm status deluge
```

### Output (Connected)

```
Deluge Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Host:       127.0.0.1:58846
Status:     ✓ Connected
Version:    2.1.1
Torrents:   146 total
  Seeding:    98
  Downloading: 12
  Paused:     36
```

### Output (Failed)

```
Deluge Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Host:       127.0.0.1:58846
Status:     ✗ Connection failed

Error: Connection refused - is deluged running?

Troubleshooting:
  1. Start deluged: deluged
  2. Check port: JMM_DELUGE_PORT
  3. Run: jmm setup deluge
```

---

## jmm status tmdb

Check TMDb API connection.

### Usage

```bash
jmm status tmdb
```

### Output

```
TMDb Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
API Key:    ✓ Configured
Status:     ✓ Connected
Test:       Found "The Matrix (1999)"
```

---

## jmm status opensubtitles

Check OpenSubtitles API status.

### Usage

```bash
jmm status opensubtitles
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

## jmm status trash

Show contents of the trash directory.

### Usage

```bash
jmm status trash
```

### Output

```
Trash Contents
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#   Date         Size    Name
──────────────────────────────────────────────────────────
1   2024-01-15   4.2 GB  The.Matrix.1999.720p.HDTV.mkv
2   2024-01-15   1.1 GB  Breaking.Bad.S01E01.480p.mkv
3   2024-01-14   2.8 GB  Movie.2023.DVDRip.avi
──────────────────────────────────────────────────────────
Total: 3 files, 8.1 GB

Use 'jmm trash restore <#>' to restore a file.
Use 'jmm status empty-trash' to permanently delete.
```

---

## jmm status empty-trash

Permanently delete files from trash.

### Usage

```bash
jmm status empty-trash [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--older-than`, `-d` | (all) | Only delete files older than N days |
| `--force`, `-f` | false | Don't ask for confirmation |

### Examples

```bash
# Empty all trash (with confirmation)
jmm status empty-trash

# Empty without confirmation
jmm status empty-trash --force

# Only delete files older than 30 days
jmm status empty-trash --older-than 30

# Combine options
jmm status empty-trash -d 7 -f
```

### Output

```
Emptying trash...

Files to delete:
  The.Matrix.1999.720p.HDTV.mkv (4.2 GB)
  Breaking.Bad.S01E01.480p.mkv (1.1 GB)
  Movie.2023.DVDRip.avi (2.8 GB)

Total: 3 files, 8.1 GB

Delete permanently? [y/N]: y

✓ Deleted 3 files, freed 8.1 GB
```

---

## Quick Reference

| Check | Command |
|-------|---------|
| All config | `jmm status config` |
| Deluge | `jmm status deluge` |
| TMDb | `jmm status tmdb` |
| Subtitles | `jmm status opensubtitles` |
| Trash | `jmm status trash` |

---

## Related Pages

- [Configuration](Configuration) - All settings
- [Setup Deluge](Setup-Deluge) - Deluge configuration
- [Setup TMDb](Setup-TMDb) - TMDb setup
- [Setup OpenSubtitles](Setup-OpenSubtitles) - Subtitles setup
- [Commands: trash](Commands-Trash) - Trash management
