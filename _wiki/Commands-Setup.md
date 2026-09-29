# jmm setup

Configure external services interactively.

## Overview

The setup command provides an interactive way to configure JackMediaMan's external service integrations.

## Usage

```bash
jmm setup [SERVICE]
```

## Subcommands

| Command | Description |
|---------|-------------|
| `jmm setup` | Show service status overview |
| `jmm setup tmdb` | Configure TMDb API key |
| `jmm setup deluge` | Configure Deluge daemon |
| `jmm setup opensubtitles` | Configure OpenSubtitles API |

---

## jmm setup

Show status of all services.

### Usage

```bash
jmm setup
```

### Output

```
JackMediaMan Services
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Service         Status          Notes
──────────────────────────────────────────────────────────
TMDb            ✓ Configured    For matching & artwork
OpenSubtitles   ✗ Not set       For subtitle downloads
Deluge          ✓ Connected     For seeding protection

To configure a service:
  jmm setup tmdb
  jmm setup opensubtitles
  jmm setup deluge
```

---

## jmm setup tmdb

Configure TMDb API key interactively.

### Usage

```bash
jmm setup tmdb
```

### Interactive Flow

```
TMDb Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TMDb (The Movie Database) provides:
  • Accurate movie/TV matching
  • Episode titles and metadata
  • Poster artwork downloads

Get your API key:
  1. Create account at themoviedb.org
  2. Go to Settings > API
  3. Request a Developer API key

Enter TMDb API Key: ****************************************

Testing connection...

✓ Connected successfully!
  Test search: "The Matrix (1999)" found

Configuration saved to ~/.jackmediaman.env
```

---

## jmm setup opensubtitles

Configure OpenSubtitles API key interactively.

### Usage

```bash
jmm setup opensubtitles
```

### Interactive Flow

```
OpenSubtitles Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OpenSubtitles provides:
  • Automatic subtitle downloads
  • File hash matching (accurate)
  • Multiple language support

Get your API key:
  1. Register at opensubtitles.com
  2. Go to opensubtitles.com/en/consumers
  3. Create an application

Enter OpenSubtitles API Key: ********************************

Preferred languages (comma-separated, e.g., en,es,fr): en,es

Testing connection...

✓ Connected successfully!
  Remaining downloads today: 200/200

Configuration saved to ~/.jackmediaman.env
```

---

## jmm setup deluge

Configure Deluge daemon connection interactively.

### Usage

```bash
jmm setup deluge
```

### Interactive Flow

```
Deluge Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Deluge integration provides:
  • Protection for seeding files
  • Torrent management commands
  • Automation via Execute plugin

Enter Deluge host [127.0.0.1]: 127.0.0.1
Enter Deluge port [58846]: 58846
Enter username [localclient]: localclient
Enter password: ********

Testing connection...

✓ Connected successfully!
  Deluge version: 2.1.1
  Active torrents: 146

Configuration saved to ~/.jackmediaman.env
```

---

## Where Settings Are Saved

All settings are saved to `~/.jackmediaman.env`:

```env
# TMDb
JMM_TMDB_API_KEY=your_tmdb_key

# OpenSubtitles
JMM_OPENSUBTITLES_API_KEY=your_opensubtitles_key
JMM_SUBTITLE_LANGUAGES=en,es

# Deluge
JMM_DELUGE_HOST=127.0.0.1
JMM_DELUGE_PORT=58846
JMM_DELUGE_USERNAME=localclient
JMM_DELUGE_PASSWORD=your_password
```

---

## Manual Configuration

You can also edit the config file directly:

```bash
nano ~/.jackmediaman.env
```

See [Configuration](Configuration) for all available settings.

---

## Reconfiguring Services

Run setup again to update credentials:

```bash
# Update TMDb key
jmm setup tmdb

# Update Deluge connection
jmm setup deluge
```

Existing settings are shown as defaults.

---

## Verifying Configuration

After setup, verify with status commands:

```bash
jmm status config        # Overview
jmm status tmdb          # TMDb specifically
jmm status opensubtitles # OpenSubtitles specifically
jmm status deluge        # Deluge specifically
```

---

## Related Pages

- [Setup TMDb](Setup-TMDb) - Detailed TMDb guide
- [Setup OpenSubtitles](Setup-OpenSubtitles) - Detailed subtitles guide
- [Setup Deluge](Setup-Deluge) - Detailed Deluge guide
- [Configuration](Configuration) - All settings
- [Commands: status](Commands-Status) - Check service status
