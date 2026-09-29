# JackMediaMan - Feature Roadmap

A complete FileBot replacement built in Python.

---

## Status Overview

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Duplicate Cleanup | ✅ Complete |
| 2 | Media Renaming | ✅ Complete |
| 3 | Subtitle Management | ✅ Complete |
| 4 | Archive Extraction | ✅ Complete |
| 5 | File Verification | 📋 Planned |
| 6 | Watch Folder Automation | ⚡ Partial (Deluge only) |
| 7 | Metadata & Artwork | ⚡ Partial (posters only) |
| 8 | Remote Operations | 📋 Planned |
| 9 | Web UI Dashboard | ✅ Complete |
| 10 | ~~Music Support~~ | ❌ Removed |
| 11 | NFO Metadata Support | 📋 Planned (NEW) |
| 12 | Enhanced Media Types | 📋 Planned (NEW) |
| 13 | Symlink Lifecycle | 📋 Planned (NEW) |

**Legend:** ✅ Complete | ⚡ Partial | 📋 Planned | ❌ Removed

---

## Completed Phases

### Phase 1: Duplicate Cleanup ✅
- [x] Project structure
- [x] Scan TV/Movies for duplicates
- [x] Quality-based ranking (resolution, source, codec, HDR)
- [x] Symlink/Deluge protection
- [x] Rich CLI interface
- [x] Dry-run and execute modes
- [x] Trash management with restore

### Phase 2: Media Renaming ✅
- [x] Auto-match media files via TMDb
- [x] Plex/Kodi naming formats
- [x] Support for TV and Movies
- [x] Actions: move, copy, symlink, hardlink, keeplink
- [x] Undo capability

### Phase 3: Subtitle Management ✅
- [x] OpenSubtitles.org (XML-RPC) integration
- [x] OpenSubtitles.com (REST API) integration
- [x] Language preferences
- [x] Hash-based matching

### Phase 4: Archive Extraction ✅
- [x] Extract RAR, ZIP, 7z archives
- [x] Multi-volume RAR support
- [x] Skip samples and proofs
- [x] Integrated in processing pipeline

### Phase 7: Metadata & Artwork ⚡ (Partial)
- [x] Download poster images from TMDb
- [x] Save as sidecar files for Plex/Kodi
- [ ] Generate NFO files for Kodi (see Phase 11)
- [ ] FanArt.tv integration
- [ ] Embed metadata in MKV containers

### Phase 9: Web UI Dashboard ✅
- [x] FastAPI REST backend
- [x] React + TypeScript frontend
- [x] Dashboard with service status
- [x] Command execution
- [x] Settings editor
- [x] Activity monitoring

---

## Remaining Phases

### Phase 5: File Verification
Replicate FileBot's `-check` functionality.

#### Features
- Verify CRC32, MD5, SHA-1, SHA-256 checksums
- Generate SFV/MD5/SHA files
- Verify against .sfv files in scene releases
- Detect corrupted downloads

#### Architecture

```
Models:
- ChecksumFile (path, algorithm, expected_hash, verified)
- VerificationResult (file, passed, expected, actual)

Services:
- HashCalculator: Compute hashes (CRC32, MD5, SHA1, SHA256)
- SFVParser: Parse .sfv files from scene releases
- VerificationService: Compare calculated vs expected hashes

CLI Commands:
- jmm verify scan <path>     # Find .sfv/.md5 files and verify
- jmm verify check <file>    # Verify single file against hash
- jmm verify generate <path> # Generate checksum file
```

#### Implementation Notes
- Use Python's hashlib for MD5/SHA
- Use binascii.crc32 for CRC32
- Parse SFV format: `filename.ext ABCD1234`
- Support recursive scanning

---

### Phase 6: Watch Folder Automation ⚡ (Partial)
Replicate FileBot's AMC (Automatic Media Center) script.

#### Current Status
- [x] Deluge Execute plugin integration (auto-triggers `jmm process` on torrent completion)
- [x] Plex library refresh notifications
- [ ] inotify file watching (real-time folder monitoring)
- [ ] qBittorrent completion hooks
- [ ] Cron-based scanning
- [ ] Notification service (Discord, Pushover, email)

#### Remaining Features
- Monitor download folders for new files (without Deluge)
- Send notifications on success/failure
- Support non-Deluge torrent clients

#### Architecture

```
Services:
- FolderWatcher: inotify-based monitoring (watchdog library)
- CronScheduler: Periodic scanning (APScheduler)
- NotificationService: Multi-provider notifications
  - Pushover
  - Discord webhooks
  - Email (SMTP)
  - Gotify

Config:
[automation]
watch_enabled = true
watch_dirs = ["~/torrents/completed"]
watch_delay = 30  # seconds to wait after file appears
cron_enabled = false
cron_schedule = "0 */6 * * *"  # every 6 hours

[notifications]
enabled = true
on_success = true
on_failure = true
providers = ["discord"]

[notifications.discord]
webhook_url = "https://discord.com/api/webhooks/..."

[notifications.pushover]
user_key = ""
api_token = ""
```

#### CLI Commands
```bash
jmm watch start       # Start daemon mode
jmm watch stop        # Stop daemon
jmm watch status      # Show watch status
jmm watch test        # Test notifications
```

---

### Phase 8: Remote Operations
Replicate FileBot's FTP/SFTP features.

#### Features
- Transfer files via FTP/SFTP/SCP
- Remote rename operations
- SSH command execution
- Seedbox integration
- Progress monitoring

#### Architecture

```
Services:
- RemoteConnection: Abstract base for FTP/SFTP
- FTPClient: FTP/FTPS transfers (ftplib)
- SFTPClient: SFTP transfers (paramiko)
- SCPClient: SCP transfers (paramiko)
- RemoteProcessor: Execute JMM commands on remote

Config:
[remote]
enabled = false
protocol = "sftp"  # ftp, sftp, scp
host = "seedbox.example.com"
port = 22
username = ""
password = ""  # or key_file
key_file = "~/.ssh/id_rsa"
remote_path = "/downloads/completed"
local_path = "~/media"

CLI Commands:
jmm remote list                  # List remote files
jmm remote sync                  # Sync remote to local
jmm remote process <path>        # Process remote torrent
jmm remote status                # Connection status
```

#### Implementation Notes
- Use paramiko for SFTP/SCP
- Use ftplib for FTP
- Support resume for interrupted transfers
- Show transfer progress with Rich

---

### ~~Phase 10: Music Support~~ (Removed)
*Not implementing - out of scope for this project.*

---

## New Phases (From olaris-renamer Analysis)

These features were identified from analyzing olaris-renamer issues and user requests.

### Phase 11: NFO Metadata Support
*Inspired by olaris-renamer issue #20*

Read and write Kodi-style .nfo XML metadata files for improved identification accuracy.

#### Overview
NFO files are XML metadata files used by Kodi/XBMC that contain:
- TMDb/IMDb/TVDb IDs
- Title, year, plot, rating
- Cast and crew information
- Poster/fanart paths

Using NFO files provides more reliable identification than filename parsing alone.

#### File Formats

**movie.nfo** (placed in movie folder):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>Dune</title>
  <year>2021</year>
  <tmdbid>438631</tmdbid>
  <imdbid>tt1160419</imdbid>
  <plot>Paul Atreides leads a guerrilla war...</plot>
  <rating>8.0</rating>
  <thumb>poster.jpg</thumb>
</movie>
```

**tvshow.nfo** (placed in series root folder):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<tvshow>
  <title>Breaking Bad</title>
  <year>2008</year>
  <tmdbid>1396</tmdbid>
  <tvdbid>81189</tvdbid>
  <plot>A chemistry teacher diagnosed with cancer...</plot>
</tvshow>
```

**episode.nfo** (placed alongside episode file):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<episodedetails>
  <title>Pilot</title>
  <season>1</season>
  <episode>1</episode>
  <aired>2008-01-20</aired>
  <plot>Walter White, a chemistry teacher...</plot>
</episodedetails>
```

#### Architecture

```
Models (src/jackmediaman/models/nfo.py):
- NFOMovieMetadata
  - title: str
  - year: int
  - tmdb_id: Optional[int]
  - imdb_id: Optional[str]
  - plot: Optional[str]
  - rating: Optional[float]

- NFOTVShowMetadata
  - title: str
  - year: Optional[int]
  - tmdb_id: Optional[int]
  - tvdb_id: Optional[int]
  - plot: Optional[str]

- NFOEpisodeMetadata
  - title: str
  - season: int
  - episode: int
  - aired: Optional[date]
  - plot: Optional[str]

Services (src/jackmediaman/services/nfo.py):
- NFOReader
  - read_movie(path) -> NFOMovieMetadata
  - read_tvshow(path) -> NFOTVShowMetadata
  - read_episode(path) -> NFOEpisodeMetadata
  - find_nfo(media_path) -> Optional[Path]

- NFOWriter
  - write_movie(metadata, path)
  - write_tvshow(metadata, path)
  - write_episode(metadata, path)
```

#### Pipeline Integration
1. **Identifier Stage**: Check for .nfo file before filename parsing
   - If NFO exists and has TMDb/TVDb ID, use that directly
   - Falls back to filename parsing if no NFO found

2. **Post-Process Hook**: Option to generate NFO after successful identification
   - Stores TMDb/IMDb IDs for future runs
   - Improves subsequent identification speed

#### CLI Commands
```bash
jmm nfo scan              # Find media missing NFO files
jmm nfo generate          # Generate NFO for all media
jmm nfo generate <path>   # Generate NFO for specific file
jmm nfo read <path>       # Display NFO contents
```

#### Configuration
```toml
[nfo]
enabled = true
read_on_identify = true   # Use NFO during identification
write_after_process = false  # Generate NFO after processing
overwrite_existing = false
```

---

### Phase 12: Enhanced Media Type Support
*Inspired by olaris-renamer issues #3, #19*

Better support for anime and daily shows.

#### 12A: Anime Support

**Problem:** Anime often uses:
- Absolute episode numbering (Episode 145 instead of S03E20)
- Episodes 100+ (current regex may fail)
- Group tags in brackets [SubGroup]
- Quality in brackets [1080p]

**Features:**
- AniDB API integration
- Absolute episode numbering support
- Season pack detection for anime
- Anime-specific naming patterns
- Handle 3+ digit episode numbers

**Architecture:**

```
Services (src/jackmediaman/services/anidb.py):
- AniDBService
  - search(title) -> List[AnimeResult]
  - get_anime(anidb_id) -> AnimeMetadata
  - get_episode(anidb_id, ep_num) -> EpisodeMetadata
  - map_to_tvdb(anidb_id) -> Optional[int]

Models:
- AnimeMetadata
  - anidb_id: int
  - title: str
  - title_romaji: Optional[str]
  - title_english: Optional[str]
  - episode_count: int
  - type: str  # TV, Movie, OVA, Special

Regex Updates (src/jackmediaman/core/parser.py):
- Episode pattern: r'[Ee](?:p(?:isode)?)?[\s._-]*(\d{1,4})'
- Group pattern: r'^\[([^\]]+)\]'
- Quality in brackets: r'\[(\d{3,4}p)\]'
```

**Naming Formats:**
```python
# Anime presets
{anime_plex}  = "{n}/Season {s}/{n} - S{s00}E{e00} - {t}"
{anime_abs}   = "{n}/{n} - {e000} - {t}"  # Absolute numbering
```

#### 12B: Daily Show Support

**Problem:** Daily shows use dates instead of season/episode:
- `Jeopardy.2019.11.19.720p.HDTV.mkv`
- `The.Daily.Show.2024.01.15.Guest.Name.mkv`

Current behavior incorrectly assigns Season 00 (specials).

**Features:**
- Detect date-based episode patterns
- Multiple date formats (YYYY.MM.DD, DD.MM.YYYY)
- Organization options:
  - Group by year as seasons
  - Flat structure with dates
- TheTVDB daily show support

**Architecture:**

```
Models:
- DailyEpisode(Episode)
  - air_date: date
  - guest: Optional[str]

Parser Updates:
- Date patterns:
  - r'(\d{4})[._-](\d{2})[._-](\d{2})'  # YYYY.MM.DD
  - r'(\d{2})[._-](\d{2})[._-](\d{4})'  # DD.MM.YYYY

Config:
[daily_shows]
organization = "by_year"  # "by_year" or "flat"
# by_year: Show Name/Season 2024/Show - 2024-01-15.mkv
# flat: Show Name/Show - 2024-01-15.mkv
```

**CLI Updates:**
```bash
jmm process run <path> --media-type daily  # Force daily show handling
```

#### 12C: Edge Case Identification

**Problem:** Numeric titles like "1917" get misidentified (olaris issue #14).

**Solution:**
- Prioritize TMDb lookup over filename parsing for ambiguous titles
- Add confidence scoring to identification
- Manual override option

```bash
jmm process run <path> --tmdb-id 530915  # Force specific TMDb ID
jmm identify <path>                       # Show identification confidence
```

---

### Phase 13: Symlink Lifecycle Management
*Inspired by olaris-renamer issue #16*

Manage symlinks throughout their lifecycle, including dead link detection and quality upgrades.

#### Overview
When using symlink/keeplink modes, links can become orphaned when:
- Original torrent is deleted
- Better quality version becomes available
- Source path changes

This phase adds tools to detect, repair, and upgrade symlinks.

#### Features

**Dead Symlink Detection:**
- Scan library for broken symlinks
- Identify orphaned links (target doesn't exist)
- Report with age and original target info

**Quality Upgrade Replacement:**
- When duplicate detected, check if lower quality is a symlink
- Automatically replace symlink target with better quality file
- Preserve seeding protection

**Cleanup Automation:**
- Auto-remove dead symlinks on schedule
- Option to move dead links to trash instead of delete

#### Architecture

```
Services (src/jackmediaman/services/symlinks.py):
- SymlinkScanner
  - find_dead_links(path) -> List[DeadLink]
  - find_all_links(path) -> List[SymlinkInfo]
  - get_link_age(path) -> timedelta

- SymlinkManager
  - repair_link(link, new_target)
  - remove_dead_links(links, to_trash=True)
  - upgrade_link(link, better_quality_file)

Models:
- SymlinkInfo
  - path: Path
  - target: Path
  - is_valid: bool
  - created: datetime

- DeadLink(SymlinkInfo)
  - original_target: str
  - age: timedelta
```

#### Integration with Duplicates

When `jmm duplicates clean` finds a duplicate:
1. Check if lower-quality version is a symlink
2. If yes, offer to update symlink target instead of removing
3. Preserves library structure while upgrading quality

```python
# Example flow:
# Library: /media/Movies/Dune (2021)/Dune.mkv -> /torrents/Dune.720p.mkv
# New download: /torrents/Dune.2021.1080p.BluRay.mkv
#
# Instead of removing 720p:
# Update symlink: /media/Movies/Dune (2021)/Dune.mkv -> /torrents/Dune.2021.1080p.BluRay.mkv
```

#### CLI Commands
```bash
jmm links scan              # Find all symlinks, report status
jmm links dead              # List dead/broken symlinks
jmm links repair            # Interactive repair of dead links
jmm links clean             # Remove dead links (to trash)
jmm links upgrade           # Scan for quality upgrades
```

#### Configuration
```toml
[symlinks]
auto_clean_dead = false    # Auto-remove dead links
clean_to_trash = true      # Move to trash vs permanent delete
upgrade_on_duplicate = true  # Auto-upgrade when duplicate found
```

---

## Additional Database Sources

### TheTVDB Integration
- Alternative to TMDb for TV shows
- Required for some anime mappings
- Episode air dates and titles

### AniDB Integration
- Primary source for anime metadata
- Absolute episode numbering
- Group/fansub information
- Cross-reference with TVDb

### OMDb Integration
- Alternative movie database
- IMDb ratings
- Rotten Tomatoes scores

### FanArt.tv Integration
- High-quality artwork
- Fanart, banners, logos
- Season posters
- Character art

---

## FileBot CLI Reference

For feature parity, here are all FileBot commands:

### Primary Commands
| FileBot | JackMediaMan | Status |
|---------|--------------|--------|
| `-rename` | `jmm rename` | ✅ Implemented |
| `-get-subtitles` | `jmm subtitles` | ✅ Implemented |
| `-check` | `jmm verify` | 📋 Phase 5 |
| `-extract` | `jmm process` (pipeline) | ✅ Implemented |
| `-list` | `jmm process list` | ✅ Implemented |
| `-find` | (use glob/grep) | N/A |
| `-mediainfo` | `jmm info` | 📋 Planned |
| `-script` | `jmm watch` | 📋 Phase 6 |
| `-revert` | `jmm rename undo` | ✅ Implemented |

### Options
| FileBot | JackMediaMan | Status |
|---------|--------------|--------|
| `--db` | `--source` | ✅ (TMDb) |
| `--format` | `--format` | ✅ Implemented |
| `--action` | `--action` | ✅ Implemented |
| `--conflict` | `--conflict` | 📋 Planned |
| `--output` | (config paths) | ✅ Implemented |
| `--lang` | `--lang` | ✅ Implemented |
| `-non-strict` | `--fuzzy` | 📋 Planned |
| `-r` | `--recursive` | ✅ Implemented |

---

## Technical Notes

### Database Caching
- [x] Cache TMDb responses locally
- [x] TTL-based expiration (24h default)
- [x] SQLite backend
- [ ] TheTVDB caching
- [ ] AniDB caching

### Rate Limiting
- [x] TMDb: 0.35s between requests
- [x] OpenSubtitles: Configurable delay
- [ ] AniDB: Respect rate limits
- [ ] FanArt.tv: Rate limiting

### File Operations
- [x] Atomic moves within same filesystem
- [x] Copy + delete for cross-filesystem
- [x] Preserve timestamps and permissions
- [x] Symlink and hardlink support

### Logging
- [x] Rich console output
- [x] Operation history in trash
- [ ] Structured JSON logs
- [ ] Configurable verbosity levels

---

## Priority Order for Implementation

Based on user demand from olaris-renamer and practical utility:

1. **Phase 11: NFO Support** - High user demand, improves identification
2. **Phase 13: Symlink Lifecycle** - Common pain point for torrent users
3. **Phase 12: Enhanced Media Types** - Anime/daily show support requested
4. **Phase 6: Watch Folder Automation** - Notifications, inotify, qBittorrent
5. **Phase 5: File Verification** - Useful for scene releases
6. **Phase 8: Remote Operations** - Niche use case (seedbox users)
