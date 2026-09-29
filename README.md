# JackMediaMan

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python CLI tool for managing media libraries - organize, rename, and deduplicate your media collection. Designed as a FileBot/Olaris replacement for users who download media via torrents.

## Features

- **Interactive Mode** - Clean terminal menu system with numbered options (`jmm -i`)
- **REST API** - FastAPI backend for automation and future web UI (`jmm --web`)
- **Zero-Config Setup** - Auto-discovers Plex (token, URL, library paths) and configures Deluge automatically
- **Duplicate Detection** - Find and remove duplicate TV episodes and movies, keeping the highest quality version
- **Torrent Processing** - Full pipeline: extract archives, identify media, organize, download subtitles and artwork
- **Media Renaming** - Standardize filenames to Plex/Kodi-friendly format
- **Subtitle Downloads** - Automatic subtitle downloads from OpenSubtitles
- **Artwork Downloads** - Download poster artwork from TMDb
- **Deluge Integration** - Protect actively seeding files and manage torrents
- **Seeding Protection** - Never accidentally delete files that are still seeding
- **Plex Notifications** - Automatic library scans when media is added or changed

## Installation

### Quick Install (Recommended)

**One-liner with auto-setup:**
```bash
pip install --user jackmediaman && ~/.local/bin/jmm setup init
```

This automatically:
- Discovers your Plex installation (token, URL, library paths)
- Configures Deluge Execute plugin for automatic processing
- Sets up Movies and TV directories from your Plex libraries

**Or use the installer script:**
```bash
curl -sSL https://raw.githubusercontent.com/jackneil/jackmediaman/main/install.sh | bash
```

### Manual Installation

**From PyPI:**
```bash
pip install --user jackmediaman
~/.local/bin/jmm setup shell   # Configure PATH (one-time)
source ~/.bashrc               # Or start new terminal
jmm setup init                 # Run auto-setup
```

**From GitHub (Latest):**
```bash
pip install --user git+https://github.com/jackneil/jackmediaman.git
~/.local/bin/jmm setup shell
source ~/.bashrc
jmm setup init
```

**From Source:**
```bash
git clone https://github.com/jackneil/jackmediaman.git
cd jackmediaman
pip install --user -e .
~/.local/bin/jmm setup shell
source ~/.bashrc
jmm setup init
```

## Quick Start

After installation with auto-setup, JackMediaMan is ready to use:

```bash
jmm                    # Show configuration status
jmm -i                 # Launch interactive menu
jmm process run PATH   # Process a torrent/media file
jmm --help             # Show all commands
```

For manual configuration, copy and edit the sample config:
```bash
cp sample.env ~/.jackmediaman.env
# Edit ~/.jackmediaman.env with your settings
```

## Configuration

### Auto-Discovery (Recommended)

Run `jmm setup init` to automatically configure:
- **Plex token** - Read from `Preferences.xml`
- **Plex URL/port** - Extracted from Plex config
- **Movies directory** - From your Plex movie library
- **TV directory** - From your Plex TV library
- **Deluge Execute plugin** - Hook for automatic torrent processing

### Manual Configuration

Create `~/.jackmediaman.env` with your settings:

```env
# Media library paths (auto-discovered from Plex if using setup init)
JMM_TV_DIR=/path/to/TV Shows
JMM_MOVIES_DIR=/path/to/Movies
JMM_TORRENT_DIR=/path/to/torrents/completed

# Optional: API keys for enhanced features
JMM_TMDB_API_KEY=your_key          # For matching & artwork
JMM_OPENSUBTITLES_API_KEY=your_key # For subtitles

# Optional: Deluge for seeding protection
JMM_DELUGE_HOST=127.0.0.1
JMM_DELUGE_PORT=58846
JMM_DELUGE_USERNAME=localclient
JMM_DELUGE_PASSWORD=your_password

# Plex (auto-discovered if using setup init)
JMM_PLEX_URL=http://localhost:32400
JMM_PLEX_API_TOKEN=           # Leave empty for auto-discovery
JMM_PLEX_NOTIFY_ENABLED=true
```

See the [wiki](../../wiki/Configuration) for all configuration options.

## Commands

| Command | Description |
|---------|-------------|
| `jmm duplicates` | Find and clean duplicate media files |
| `jmm process` | Process completed torrent downloads |
| `jmm rename` | Rename media files to standard format |
| `jmm subtitles` | Download subtitles from OpenSubtitles |
| `jmm artwork` | Download poster artwork from TMDb |
| `jmm torrents` | Manage Deluge torrents |
| `jmm status` | Check configuration and service status |
| `jmm setup` | Configure external services |

### Common Examples

```bash
# Find duplicates
jmm duplicates scan

# Process a completed torrent (with keeplink for seeding)
jmm process run /downloads/Movie.2024.1080p --action keeplink

# Preview file renames
jmm rename preview

# Download subtitles for your library
jmm subtitles download --type both

# Check service status
jmm status config
```

## Interactive Mode

Launch a clean, organized terminal interface with numbered menus:

```bash
jmm -i           # Launch interactive mode
jmm interactive  # Same as above
```

**Features:**
- **Grouped Menus** - Library operations, status, and configuration sections
- **Status Bar** - Real-time service indicators (TMDb, Deluge, OpenSubtitles)
- **Sub-menus** - Each command has its own menu for options
- **Clean Navigation** - Numbered options with [0] to go back

The interactive mode uses Rich for beautiful terminal output and doesn't require any additional dependencies.

## REST API

JackMediaMan includes a FastAPI backend for automation and scripting:

```bash
jmm --web               # Start API server at http://localhost:8080
jmm --web --port 9000   # Custom port
```

**Endpoints:**
- `GET /api/status` - Service status and library stats
- `GET /api/commands` - List available commands
- `POST /api/commands/{name}/execute` - Execute commands
- `GET/PUT /api/settings` - View and edit configuration

> Requires: `pip install jackmediaman[web]`

See the [Web Interface Guide](../../wiki/Web-Interface) for full documentation.

## API Keys

JackMediaMan works without API keys but is enhanced with them:

### TMDb (Recommended)
For accurate movie matching, TV metadata, and artwork:
1. Create account at [themoviedb.org](https://www.themoviedb.org/)
2. Go to Settings > API > Request API key
3. Run `jmm setup tmdb`

### OpenSubtitles (Optional)
For automatic subtitle downloads:
1. Register at [opensubtitles.com](https://www.opensubtitles.com/)
2. Go to [Consumers](https://www.opensubtitles.com/en/consumers) for API key
3. Run `jmm setup opensubtitles`

### Deluge (Optional)
For seeding protection and torrent management:
1. Ensure deluged is running
2. Run `jmm setup deluge`

See the [wiki](../../wiki) for detailed setup guides.

## Quality Scoring

When finding duplicates, files are ranked by quality:

| Factor | Score |
|--------|-------|
| 4K/2160p | 4000 |
| 1080p | 3000 |
| 720p | 2000 |
| BluRay | +60 |
| WEB-DL | +40 |
| x265/HEVC | +12 |
| HDR | +20 |

The highest-scored file is kept; lower-quality duplicates are moved to trash.

## Documentation

Full documentation is available in the [wiki](../../wiki):

- [Installation](../../wiki/Installation)
- [Configuration](../../wiki/Configuration)
- [Web Interface](../../wiki/Web-Interface)
- [Commands Reference](../../wiki/Commands)
- [Deluge Setup](../../wiki/Setup-Deluge)
- [Troubleshooting](../../wiki/Troubleshooting)

## Contributing

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/jackmediaman

# Linting
ruff check src/
```

## License

MIT
