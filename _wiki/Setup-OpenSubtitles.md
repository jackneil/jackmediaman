# OpenSubtitles Setup

This guide covers setting up OpenSubtitles integration with JackMediaMan for automatic subtitle downloads.

## Overview

OpenSubtitles integration provides:

- **Automatic subtitle downloads** - Download subtitles for movies and TV shows
- **Hash-based matching** - Accurate matching using file hash (not just filename)
- **Multi-language support** - Download subtitles in multiple languages
- **Batch operations** - Download subtitles for entire directories or libraries

## When Do You Need This?

- If you want automatic subtitles when processing torrents
- If you want to batch-download subtitles for existing media
- If you watch content in non-native languages

---

## Provider Options

JackMediaMan supports two OpenSubtitles providers:

| Provider | API | Requirements | Notes |
|----------|-----|--------------|-------|
| **OpenSubtitles.org** | XML-RPC | Username + Password | Default, simpler setup |
| **OpenSubtitles.com** | REST | API Key + Username + Password | Free tier available |

### Which Provider Should I Use?

- **OpenSubtitles.org** - Use if you already have an account. Just username/password needed.
- **OpenSubtitles.com** - Use if you prefer the REST API or need a free account. Requires registering an application to get an API key.

---

## Option 1: OpenSubtitles.org (Default)

### Step 1: Create an Account

1. Go to [opensubtitles.org](https://www.opensubtitles.org/)
2. Click "Register" in the top right
3. Fill in your details and verify your email

### Step 2: Configure JackMediaMan

**Interactive setup (recommended):**
```bash
jmm setup opensubtitles
```

When prompted:
- **Provider:** `org` (default)
- **Username:** Your OpenSubtitles.org username
- **Password:** Your OpenSubtitles.org password

**Manual configuration:**

Add to `~/.jackmediaman.env`:
```env
JMM_OPENSUBTITLES_PROVIDER=org
JMM_OPENSUBTITLES_USERNAME=your_username
JMM_OPENSUBTITLES_PASSWORD=your_password
JMM_SUBTITLE_LANGUAGES=en
```

### Step 3: Verify

```bash
jmm setup
```

Look for:
```
OpenSubtitles     your_username (.org)
```

---

## Option 2: OpenSubtitles.com

### Step 1: Create an Account

1. Go to [opensubtitles.com](https://www.opensubtitles.com/)
2. Click "Register" in the top right
3. Fill in your details and verify your email

### Step 2: Get an API Key

1. Log in to your account
2. Go to [Consumers](https://www.opensubtitles.com/en/consumers)
3. Click "Create new App"
4. Fill in the application form:
   - **App Name:** JackMediaMan
   - **Description:** Personal media library management
5. Note your **API Key**

### Step 3: Configure JackMediaMan

**Interactive setup (recommended):**
```bash
jmm setup opensubtitles
```

When prompted:
- **Provider:** `com`
- **Username:** Your OpenSubtitles.com username
- **Password:** Your OpenSubtitles.com password
- **API Key:** Your application API key

**Manual configuration:**

Add to `~/.jackmediaman.env`:
```env
JMM_OPENSUBTITLES_PROVIDER=com
JMM_OPENSUBTITLES_USERNAME=your_username
JMM_OPENSUBTITLES_PASSWORD=your_password
JMM_OPENSUBTITLES_API_KEY=your_api_key
JMM_SUBTITLE_LANGUAGES=en
```

### Step 4: Verify

```bash
jmm setup
```

Look for:
```
OpenSubtitles     your_username (.com)
```

### JWT Token Caching

For the `.com` provider, JackMediaMan automatically caches your JWT authentication token for 24 hours. This means:
- You don't need to log in for every request
- Token is stored in `~/.jackmediaman.env`
- Automatically refreshed when expired

---

## Configuration Options

### Language Preferences

Set your preferred subtitle languages (comma-separated ISO 639-1 codes):

```env
JMM_SUBTITLE_LANGUAGES=en,es,fr
```

Common language codes:
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

JackMediaMan downloads subtitles in order of preference. If English subtitles aren't found, it tries Spanish, then French, etc.

---

## Using Subtitle Features

### Download for Single File

```bash
jmm subtitles download /path/to/movie.mkv
```

### Download for Directory

```bash
jmm subtitles download /path/to/show/Season\ 01/
```

### Download for Entire Library

```bash
# TV shows only
jmm subtitles download --type tv

# Movies only
jmm subtitles download --type movies

# Both
jmm subtitles download --type both
```

### Options

```bash
# Specify languages (override config)
jmm subtitles download /path/to/movie.mkv -l en,es

# Overwrite existing subtitles
jmm subtitles download /path/to/movie.mkv --overwrite

# Dry run (show what would be downloaded)
jmm subtitles download /path/to/movie.mkv --dry-run
```

### In Processing Pipeline

Subtitles are automatically downloaded during `jmm process`:

```bash
# Include subtitles (default)
jmm process run /path/to/torrent

# Skip subtitle download
jmm process run /path/to/torrent --no-subtitles
```

---

## API Limits

### OpenSubtitles.org

- Rate limited to prevent abuse
- No explicit daily download limit

### OpenSubtitles.com Free Tier

- **200 downloads per day** per user
- **5 downloads per second** rate limit

JackMediaMan enforces rate limiting automatically.

### Checking Status

```bash
jmm setup
```

Shows your configured provider and username.

---

## How Matching Works

OpenSubtitles uses multiple methods to find the right subtitles:

1. **File Hash** - Most accurate. Computes hash of the video file to find exact matches.
2. **IMDB ID** - If hash fails, uses IMDB ID from TMDb lookup.
3. **Filename** - Fallback to filename-based search.

This means subtitles downloaded via JackMediaMan are usually well-synced with your specific video file.

---

## Troubleshooting

### Login Failed

**Symptoms:** `Could not log in. Please check your credentials.`

**Solutions:**
1. Verify username and password are correct
2. Make sure you're using the right provider (org vs com)
3. For .com, ensure your API key is valid

### No Subtitles Found

**Possible causes:**
1. Subtitles don't exist for this file on OpenSubtitles
2. Language not available for this title
3. File hash doesn't match any known release

**Solutions:**
1. Try a different language: `-l en,es,pt`
2. Search manually on [opensubtitles.com](https://www.opensubtitles.com/)
3. Use a different release of the video

### Download Limit Reached (OpenSubtitles.com)

**Symptoms:** `Daily download limit reached`

**Solutions:**
1. Wait until tomorrow (resets at midnight UTC)
2. Prioritize which files need subtitles
3. Consider using OpenSubtitles.org instead

### Wrong Subtitles Downloaded

**Symptoms:** Subtitles are out of sync or for wrong version

**Solutions:**
1. The file hash should prevent this, but it can happen with re-encoded files
2. Delete the subtitle and re-download
3. Search manually for alternate subtitles

---

## Subtitle File Naming

Downloaded subtitles are named to match your video file:

```
Movie (2024).mkv
Movie (2024).en.srt      # English subtitles
Movie (2024).es.srt      # Spanish subtitles
```

Most media players (Plex, Kodi, VLC) auto-detect these sidecar subtitles.

---

## Quick Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `JMM_OPENSUBTITLES_PROVIDER` | `org` | Provider: `org` or `com` |
| `JMM_OPENSUBTITLES_USERNAME` | (none) | Your OpenSubtitles username |
| `JMM_OPENSUBTITLES_PASSWORD` | (none) | Your OpenSubtitles password |
| `JMM_OPENSUBTITLES_API_KEY` | (none) | API key (OpenSubtitles.com only) |
| `JMM_SUBTITLE_LANGUAGES` | `en` | Comma-separated language codes |

## Related Pages

- [Configuration](Configuration) - All configuration options
- [Commands: subtitles](Commands-Subtitles) - Subtitle commands reference
- [Commands: process](Commands-Process) - Processing pipeline
