# JackMediaMan Wiki

Welcome to the JackMediaMan documentation - a Python CLI tool for managing media libraries.

## What is JackMediaMan?

JackMediaMan is a FileBot/Olaris replacement for organizing, renaming, and deduplicating your media collection. It's designed for users who download media via torrents and want to automatically organize files into a clean library structure while maintaining seeding capability.

## Key Features

- **[Interactive Mode](Commands#interactive-mode)** - Clean terminal menu system with grouped options (`jmm -i`)
- **[REST API](Web-Interface)** - FastAPI backend for automation and scripting (`jmm --web`)
- **[Duplicate Detection](Commands-Duplicates)** - Find and remove duplicate TV episodes and movies, keeping the highest quality version
- **[Torrent Processing](Commands-Process)** - Full pipeline for processing completed torrents: extract archives, identify media, organize, download subtitles and artwork
- **[Media Renaming](Commands-Rename)** - Standardize filenames to Plex/Kodi-friendly format
- **[Subtitle Downloads](Commands-Subtitles)** - Automatic subtitle downloads from OpenSubtitles
- **[Artwork Downloads](Commands-Artwork)** - Download poster artwork from TMDb
- **[Deluge Integration](Setup-Deluge)** - Protect actively seeding files and manage torrents
- **[Seeding Protection](Commands-Duplicates#protection)** - Never accidentally delete files that are still seeding

## Quick Start

```bash
# Install
pip install jackmediaman

# Auto-setup (discovers Plex, configures Deluge)
jmm setup init

# Launch interactive menu
jmm -i
```

## Quick Links

| Task | Command |
|------|---------|
| **Launch interactive menu** | `jmm -i` |
| Find duplicates | `jmm duplicates scan` |
| Process torrent | `jmm process run /path/to/torrent` |
| Rename media | `jmm rename preview` |
| Download subtitles | `jmm subtitles download` |
| Check configuration | `jmm status config` |
| Start REST API | `jmm --web` |

## Getting Started

1. **[Installation](Installation)** - Install JackMediaMan and dependencies
2. **[Configuration](Configuration)** - Set up your media library paths
3. **[Service Setup](Setup-TMDb)** - Configure TMDb, OpenSubtitles, Deluge (optional)
4. **[Commands](Commands)** - Learn the available commands

## Need Help?

- Check the **[Troubleshooting](Troubleshooting)** guide for common issues
- Run `jmm --help` or `jmm <command> --help` for CLI help
- Report issues at [GitHub Issues](https://github.com/jackneil/jackmediaman/issues)
