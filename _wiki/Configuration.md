# Configuration

JackMediaMan uses environment variables for configuration, loaded from `.env` files.

## Configuration Files

Settings are loaded in this order (later files override earlier):

1. `.env` in project directory
2. `~/.jackmediaman.env` (recommended location)
3. System environment variables

## Quick Setup

```bash
# Create config file
touch ~/.jackmediaman.env

# Edit with your settings
nano ~/.jackmediaman.env
```

Minimum configuration:

```env
JMM_TV_DIR=/path/to/TV Shows
JMM_MOVIES_DIR=/path/to/Movies
JMM_TORRENT_DIR=/path/to/torrents/completed
```

---

## All Configuration Options

### Media Library Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `JMM_TV_DIR` | `~/media/TV Shows` | Path to TV Shows library |
| `JMM_MOVIES_DIR` | `~/media/Movies` | Path to Movies library |
| `JMM_TRASH_DIR` | `~/.jackmediaman/trash` | Path to trash directory for removed duplicates |
| `JMM_TORRENT_DIR` | `~/torrents/completed` | Path to completed torrents directory |

**Example:**
```env
JMM_TV_DIR=/mnt/media/TV Shows
JMM_MOVIES_DIR=/mnt/media/Movies
JMM_TRASH_DIR=/mnt/media/.trash
JMM_TORRENT_DIR=/mnt/downloads/completed
```

---

### Deluge Daemon Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `JMM_DELUGE_HOST` | `127.0.0.1` | Deluge daemon hostname or IP |
| `JMM_DELUGE_PORT` | `58846` | Deluge daemon port |
| `JMM_DELUGE_USERNAME` | (empty) | Deluge authentication username |
| `JMM_DELUGE_PASSWORD` | (empty) | Deluge authentication password |

**Example:**
```env
JMM_DELUGE_HOST=192.168.1.100
JMM_DELUGE_PORT=58846
JMM_DELUGE_USERNAME=localclient
JMM_DELUGE_PASSWORD=abc123def456
```

See [Deluge Setup](Setup-Deluge) for detailed configuration guide.

---

### TMDb API Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `JMM_TMDB_API_KEY` | (none) | TMDb API v3 key |

**Example:**
```env
JMM_TMDB_API_KEY=your_api_key_here
```

See [TMDb Setup](Setup-TMDb) for how to get an API key.

---

### OpenSubtitles Settings

JackMediaMan supports both OpenSubtitles.org (XML-RPC) and OpenSubtitles.com (REST API).

| Variable | Default | Description |
|----------|---------|-------------|
| `JMM_OPENSUBTITLES_PROVIDER` | `org` | Provider: `org` or `com` |
| `JMM_OPENSUBTITLES_USERNAME` | (none) | Your OpenSubtitles username |
| `JMM_OPENSUBTITLES_PASSWORD` | (none) | Your OpenSubtitles password |
| `JMM_OPENSUBTITLES_API_KEY` | (none) | API key (OpenSubtitles.com only) |
| `JMM_SUBTITLE_LANGUAGES` | `en` | Comma-separated language codes |

**Example (OpenSubtitles.org - default):**
```env
JMM_OPENSUBTITLES_PROVIDER=org
JMM_OPENSUBTITLES_USERNAME=your_username
JMM_OPENSUBTITLES_PASSWORD=your_password
JMM_SUBTITLE_LANGUAGES=en,es,fr
```

**Example (OpenSubtitles.com):**
```env
JMM_OPENSUBTITLES_PROVIDER=com
JMM_OPENSUBTITLES_USERNAME=your_username
JMM_OPENSUBTITLES_PASSWORD=your_password
JMM_OPENSUBTITLES_API_KEY=your_api_key
JMM_SUBTITLE_LANGUAGES=en,es,fr
```

See [OpenSubtitles Setup](Setup-OpenSubtitles) for details.

---

### Cache Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `JMM_CACHE_DIR` | `~/.jackmediaman/cache` | Path to cache directory |
| `JMM_CACHE_TTL` | `86400` | Cache TTL in seconds (default 24 hours) |

**Example:**
```env
JMM_CACHE_DIR=/tmp/jmm-cache
JMM_CACHE_TTL=43200  # 12 hours
```

Cache stores:
- FFprobe metadata results
- TMDb API responses

---

### FFprobe Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `JMM_FFPROBE_ENABLED` | `true` | true/false | Enable FFprobe for quality detection |
| `JMM_FFPROBE_WORKERS` | `4` | 1-16 | Parallel workers for batch operations |
| `JMM_FFPROBE_TIMEOUT` | `30.0` | 1.0-120.0 | Timeout per file (seconds) |

**Example:**
```env
JMM_FFPROBE_ENABLED=true
JMM_FFPROBE_WORKERS=8
JMM_FFPROBE_TIMEOUT=60.0
```

FFprobe provides accurate resolution/codec detection. Without it, JackMediaMan falls back to filename parsing.

---

### Process Command Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `JMM_PROCESS_DEFAULT_ACTION` | `symlink` | Default action mode |
| `JMM_PROCESS_EXTRACT_DIR` | (system temp) | Directory for archive extraction |
| `JMM_PROCESS_CLEANUP_ARCHIVES` | `false` | Delete archives after extraction |

**Action modes:**
- `move` - Move files to library
- `copy` - Copy files (keeps original)
- `hardlink` - Create hard links (same filesystem)
- `symlink` - Create symbolic links (default)
- `keeplink` - Move to library, leave symlink at source

**Example:**
```env
JMM_PROCESS_DEFAULT_ACTION=keeplink
JMM_PROCESS_EXTRACT_DIR=/tmp/jmm-extract
JMM_PROCESS_CLEANUP_ARCHIVES=true
```

---

## Complete Example

Here's a full configuration file:

```env
# ~/.jackmediaman.env

# === Media Library Paths ===
JMM_TV_DIR=/mnt/media/TV Shows
JMM_MOVIES_DIR=/mnt/media/Movies
JMM_TRASH_DIR=/mnt/media/.jackmediaman/trash
JMM_TORRENT_DIR=/mnt/downloads/completed

# === Deluge Daemon ===
JMM_DELUGE_HOST=127.0.0.1
JMM_DELUGE_PORT=58846
JMM_DELUGE_USERNAME=localclient
JMM_DELUGE_PASSWORD=your_password_here

# === TMDb API ===
JMM_TMDB_API_KEY=your_tmdb_api_key

# === OpenSubtitles ===
JMM_OPENSUBTITLES_PROVIDER=org
JMM_OPENSUBTITLES_USERNAME=your_username
JMM_OPENSUBTITLES_PASSWORD=your_password
JMM_SUBTITLE_LANGUAGES=en,es

# === Cache Settings ===
JMM_CACHE_DIR=/mnt/media/.jackmediaman/cache
JMM_CACHE_TTL=86400

# === FFprobe Settings ===
JMM_FFPROBE_ENABLED=true
JMM_FFPROBE_WORKERS=4
JMM_FFPROBE_TIMEOUT=30.0

# === Process Settings ===
JMM_PROCESS_DEFAULT_ACTION=keeplink
JMM_PROCESS_CLEANUP_ARCHIVES=false
```

---

## Verifying Configuration

Check your current configuration:

```bash
jmm status config
```

Output shows all configured paths and service status.

---

## Configuration Tips

### Paths with Spaces

Paths with spaces work fine in the config file:
```env
JMM_TV_DIR=/mnt/Media Library/TV Shows
```

### Environment Variable Override

Override any setting with environment variables:
```bash
JMM_DRY_RUN=true jmm duplicates clean
```

### Multiple Config Files

For different setups, use different env files:
```bash
# Use alternate config
export JMM_CONFIG=~/.jackmediaman-seedbox.env
jmm status config
```

### Security

Keep API keys and passwords secure:
```bash
chmod 600 ~/.jackmediaman.env
```

---

## Related Pages

- [Installation](Installation) - Installing JackMediaMan
- [Setup TMDb](Setup-TMDb) - Getting TMDb API key
- [Setup OpenSubtitles](Setup-OpenSubtitles) - Subtitle service setup
- [Setup Deluge](Setup-Deluge) - Deluge daemon configuration
