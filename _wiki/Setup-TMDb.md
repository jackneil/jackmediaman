# TMDb API Setup

This guide covers setting up The Movie Database (TMDb) API integration with JackMediaMan.

## Overview

TMDb integration provides:

- **Accurate movie matching** - Match movies by TMDb ID instead of just filename parsing
- **TV episode metadata** - Get episode titles, air dates, and season information
- **Artwork downloads** - Download high-quality poster artwork
- **Better duplicate detection** - Avoid false positives from similar titles

## When Do You Need This?

| Feature | TMDb Required? |
|---------|---------------|
| `jmm duplicates --matcher tmdb` | Yes |
| `jmm rename` (TV episode titles) | Yes |
| `jmm artwork download` | Yes |
| `jmm process` (media identification) | Recommended |
| `jmm duplicates --matcher title_year` | No |
| `jmm duplicates --matcher fuzzy` | No |

**Without TMDb:** JackMediaMan works fine for basic operations using filename parsing. TMDb adds accuracy for edge cases and enables artwork/metadata features.

---

## Getting a TMDb API Key

### Step 1: Create an Account

1. Go to [themoviedb.org](https://www.themoviedb.org/)
2. Click "Join TMDB" in the top right
3. Fill in your details and verify your email

### Step 2: Request an API Key

1. Log in to your account
2. Go to [Settings > API](https://www.themoviedb.org/settings/api)
3. Click "Create" under "Request an API Key"
4. Select "Developer" (free tier)
5. Fill in the application form:
   - **Type of Use:** Personal
   - **Application Name:** JackMediaMan (or anything)
   - **Application URL:** https://github.com/jackusc/jackmediaman
   - **Application Summary:** Personal media library management
6. Accept the terms of use
7. Copy your **API Key (v3 auth)**

### Step 3: Configure JackMediaMan

**Option A: Interactive setup**
```bash
jmm setup tmdb
```

**Option B: Manual configuration**

Add to `~/.jackmediaman.env`:
```env
JMM_TMDB_API_KEY=your_api_key_here
```

### Step 4: Verify

```bash
jmm status tmdb
```

**Successful output:**
```
TMDb Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
API Key:    ✓ Configured
Status:     ✓ Connected
Test:       Found "The Matrix (1999)"
```

---

## API Usage & Limits

### Rate Limits

TMDb allows **40 requests per 10 seconds** on the free tier. JackMediaMan handles this automatically with:

- Request throttling
- Response caching (SQLite)
- Batch operations where possible

### Caching

API responses are cached in `~/.jackmediaman/cache/tmdb.db`:

- Movie lookups
- TV show details
- Episode metadata
- Search results

Clear cache if you need fresh data:
```bash
jmm cache clear --type tmdb
```

---

## Using TMDb Features

### Movie Matching (Duplicates)

Use TMDb for the most accurate duplicate detection:

```bash
jmm duplicates scan --matcher tmdb
```

This queries TMDb to resolve ambiguous titles like:
- "The Thing (1982)" vs "The Thing (2011)"
- "Crash (2004)" vs "Crash (1996)"

### TV Episode Renaming

Get proper episode titles:

```bash
jmm rename preview --type tv
```

Without TMDb, episode titles are omitted from filenames.

### Artwork Downloads

Download posters for your library:

```bash
# Download missing artwork
jmm artwork download --type both

# See coverage statistics
jmm artwork status
```

### Media Identification (Process)

The process pipeline uses TMDb to identify media:

```bash
jmm process run /path/to/download
```

Skip TMDb lookup if not needed:
```bash
jmm process run /path/to/download --no-tmdb
```

---

## Troubleshooting

### Invalid API Key

**Symptoms:** `401 Unauthorized` or `Invalid API key`

**Solutions:**
1. Double-check the key is copied correctly (no extra spaces)
2. Ensure you're using the v3 API key, not v4
3. Wait a few minutes if you just created the key

### Rate Limited

**Symptoms:** `429 Too Many Requests`

**Solutions:**
1. JackMediaMan auto-throttles, but if you see this:
   - Wait a minute and retry
   - Reduce batch sizes in operations
2. Check if another app is using the same API key

### Connection Errors

**Symptoms:** `Connection timeout` or `Name resolution failed`

**Solutions:**
1. Check your internet connection
2. TMDb may be temporarily down - check [status.themoviedb.org](https://status.themoviedb.org/)
3. Check if your network blocks API requests

### Wrong Movie/Show Matched

**Symptoms:** TMDb returns wrong match for a title

**Solutions:**
1. The filename may be ambiguous - rename it with the year
2. Clear cache and retry: `jmm cache clear --type tmdb`
3. For duplicates, consider using `--matcher title_year` as fallback

---

## Quick Reference

| Setting | Description |
|---------|-------------|
| `JMM_TMDB_API_KEY` | Your TMDb API v3 key |

## Related Pages

- [Configuration](Configuration) - All configuration options
- [Commands: artwork](Commands-Artwork) - Artwork download commands
- [Commands: rename](Commands-Rename) - Media renaming
- [Commands: duplicates](Commands-Duplicates) - Duplicate detection
