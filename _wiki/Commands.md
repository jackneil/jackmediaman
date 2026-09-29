# Commands Overview

JackMediaMan provides several commands for managing your media library. Run `jmm --help` for a quick reference.

## Command Summary

| Command | Description |
|---------|-------------|
| [`jmm duplicates`](Commands-Duplicates) | Find and clean duplicate media files |
| [`jmm process`](Commands-Process) | Process completed torrent downloads |
| [`jmm rename`](Commands-Rename) | Rename media files to standard format |
| [`jmm subtitles`](Commands-Subtitles) | Download subtitles from OpenSubtitles |
| [`jmm artwork`](Commands-Artwork) | Download poster artwork from TMDb |
| [`jmm torrents`](Commands-Torrents) | Manage Deluge torrents |
| [`jmm status`](Commands-Status) | Check configuration and service status |
| [`jmm setup`](Commands-Setup) | Configure external services |
| [`jmm cache`](Commands-Cache) | Manage metadata caches |
| [`jmm trash`](Commands-Trash) | Manage trash directory |

## Interactive Mode

Launch a clean, organized terminal interface with numbered menus:

```bash
jmm -i           # Launch interactive mode
jmm interactive  # Same as above
```

The interactive menu provides:

**LIBRARY OPERATIONS**
1. Process New Media - Process completed torrent downloads
2. Find Duplicates - Scan library for duplicate files
3. Rename Files - Rename media to standardized format
4. Manage Subtitles - Download subtitles for media
5. Fetch Artwork - Download poster artwork from TMDb

**STATUS & INFO**
6. Library Status - View configuration and paths
7. Service Health - Test Deluge, TMDb, OpenSubtitles
8. View Trash - Manage deleted files

**CONFIGURATION**
9. Settings - Configure paths and services
10. Setup Wizard - Initial setup for services

**Features:**
- **Status Bar** - Real-time service indicators (● green = configured, ○ dim = not configured)
- **Sub-menus** - Each option has its own detailed menu
- **Clean Navigation** - Use [0] to go back or exit

## Common Options

Most commands support these options:

| Option | Description |
|--------|-------------|
| `--help` | Show command help |
| `--dry-run` / `-n` | Preview without making changes |
| `--type` / `-t` | Filter by media type (tv, movies, both) |

## Typical Workflows

### Setting Up

```bash
# 1. Configure your settings
jmm setup tmdb          # TMDb API key
jmm setup opensubtitles # OpenSubtitles API key
jmm setup deluge        # Deluge daemon (if used)

# 2. Check configuration
jmm status config
```

### Processing New Downloads

```bash
# Preview what will happen
jmm process run /downloads/Movie.2024.1080p --dry-run

# Process for real (with symlinks)
jmm process run /downloads/Movie.2024.1080p

# Process with keeplink (move + symlink for seeding)
jmm process run /downloads/Movie.2024.1080p --action keeplink
```

### Cleaning Up Duplicates

```bash
# Scan for duplicates (preview only)
jmm duplicates scan

# Clean with confirmation
jmm duplicates clean --execute --interactive

# Automatic cleanup
jmm duplicates clean --execute --auto
```

### Organizing Existing Library

```bash
# Preview renames
jmm rename preview

# Execute renames
jmm rename execute --yes
```

### Downloading Subtitles

```bash
# Single file
jmm subtitles download /path/to/video.mkv

# Entire library
jmm subtitles download --type both
```

### Managing Torrents

```bash
# List all torrents
jmm torrents list

# Move completed to library folder
jmm torrents move --execute
```

## Getting Help

```bash
# General help
jmm --help

# Command-specific help
jmm duplicates --help
jmm process run --help
```

## Related Pages

- [Installation](Installation) - Getting started
- [Configuration](Configuration) - All settings
- Individual command pages (linked above)
