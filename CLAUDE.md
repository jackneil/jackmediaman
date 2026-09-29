# CLAUDE.md - Project Guidelines for JackMediaMan

This file provides context for Claude Code and other AI assistants working on this project.

## Project Overview

JackMediaMan is a **FileBot/Olaris replacement** for users who download media via torrents. The goal is to automatically organize, rename, and deduplicate media files while maintaining the ability to continue seeding.

**Primary use case:** User downloads a torrent → JMM processes it → Files are organized into Plex/Kodi-friendly structure → Original files remain for seeding.

## Tech Stack

- **Python 3.10+** - Target version
- **Typer** - CLI framework (modern Click alternative)
- **Rich** - Terminal UI and formatting (interactive menu system)
- **Pydantic** - Data models and settings validation
- **pydantic-settings** - Configuration from environment/`.env` files
- **FastAPI** - REST API for web interface (optional)
- **React + TypeScript** - Web UI frontend (optional)

### Key Dependencies
- `deluge-client` - Deluge daemon communication (seeding protection)
- `httpx` - HTTP client for API calls (TMDb, Plex, OpenSubtitles)
- `guessit` - Media filename parsing

## Project Structure

```
src/jackmediaman/
├── cli/           # Typer commands and interactive menu
│   ├── app.py           # Main CLI entry point
│   ├── interactive.py   # Rich-based interactive menu
│   └── commands/        # Subcommands (duplicates, process, rename, etc.)
├── core/          # Core functionality (config, settings_manager)
├── matchers/      # Duplicate matching strategies
├── models/        # Pydantic data models
├── pipeline/      # Processing pipeline stages
├── protectors/    # Seeding protection (symlink, deluge)
├── scanners/      # Library scanning
├── services/      # External service integrations
└── web/           # FastAPI web backend (optional)
    ├── api/             # REST API routes
    └── static/          # Built React app

frontend/          # React source (separate from Python package)
├── src/
│   ├── pages/           # Dashboard, Commands, Settings, Activity
│   ├── components/      # Reusable UI components
│   └── api/             # API client
```

## User Interfaces

### 1. Direct CLI Commands
```bash
jmm process run /path/to/torrent    # Process a torrent
jmm duplicates scan                  # Find duplicates
jmm status config                    # Show configuration
```

### 2. Interactive Menu (`jmm -i`)
Rich-based numbered menu system with:
- Main menu with grouped options
- Sub-menus for each command
- Clean navigation with [0] Back option
- Real-time status indicators

### 3. Web UI (`jmm --web`) - In Development
FastAPI + React SPA with:
- Dashboard with service status
- Command execution with live output
- Settings editor
- Activity/logs page

## Code Style & Preferences

### Philosophy: Minimal & Practical

**DO:**
- Keep solutions simple and straightforward
- Make it work first, optimize later if needed
- Prefer small, focused changes
- Use existing patterns in the codebase

**DON'T:**
- Over-engineer or add unnecessary abstractions
- Add features that weren't requested
- Refactor surrounding code unless asked
- Create elaborate class hierarchies for simple tasks

### Specific Guidelines

1. **Settings/Config**: Use pydantic-settings with `~/.jackmediaman.env` file
2. **CLI Commands**: Use Typer with consistent patterns from existing commands
3. **Interactive Menu**: Add new options to `cli/interactive.py` menus
4. **Error Handling**: Graceful degradation - don't crash if a service is unavailable
5. **Documentation**: Update wiki and README when adding user-facing features

## User Preferences

### UI/UX
- User prefers **clean, simple interfaces** like Sonarr/Radarr
- Real-time feedback is important (progress indicators)
- Numbered menus over complex TUI widgets
- Direct CLI commands for automation

### Feature Priorities
1. **Seeding protection** - Never delete files that are still seeding
2. **Automation** - Process torrents automatically via Deluge Execute plugin
3. **Quality detection** - Keep highest quality version of duplicates
4. **Plex integration** - Auto-discover settings, notify on changes

## Key Integrations

### Deluge
- Connect via daemon RPC (not web API)
- Used for: seeding protection, torrent management, Execute plugin automation
- Config: `JMM_DELUGE_HOST`, `JMM_DELUGE_PORT`, `JMM_DELUGE_USERNAME`, `JMM_DELUGE_PASSWORD`

### Plex
- Auto-discover token and URL from `Preferences.xml`
- Library notifications when files are added/changed
- Discover media paths from Plex libraries

### TMDb
- Movie/TV identification and metadata
- Poster artwork downloads
- Optional but recommended

### OpenSubtitles
- Automatic subtitle downloads
- Supports both .org (XML-RPC) and .com (REST API)
- Optional

## Testing

```bash
# Run tests
pytest

# Type checking
mypy src/jackmediaman

# Linting
ruff check src/
```

## Common Tasks

### Adding a new CLI command
1. Create `src/jackmediaman/cli/commands/yourcommand.py`
2. Register in `src/jackmediaman/cli/app.py` with `app.add_typer()`
3. Add menu entry in `src/jackmediaman/cli/interactive.py`

### Adding configuration options
1. Add field to `Settings` class in `src/jackmediaman/core/config.py`
2. Add to `SETTINGS_GROUPS` in `src/jackmediaman/core/settings_manager.py` for settings editor
3. Document in wiki Configuration page

## Notes

- The "keeplink" action mode creates symlinks in library but keeps originals for seeding
- Quality scoring considers resolution, codec, source, HDR, etc.
- Trash directory is used instead of permanent deletion (with restore capability)
- Cache is used for TMDb lookups to avoid rate limiting
- **Wiki documentation is in `_wiki/` folder** (not `wiki/`) - this syncs with GitHub wiki
