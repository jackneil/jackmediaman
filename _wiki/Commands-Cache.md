# jmm cache

Manage metadata caches.

## Overview

JackMediaMan caches API responses and FFprobe results to improve performance and reduce API calls. The cache command lets you view and manage these caches.

## Subcommands

| Command | Description |
|---------|-------------|
| `jmm cache stats` | Show cache statistics |
| `jmm cache clear` | Clear cache entries |
| `jmm cache cleanup` | Remove stale entries |

---

## jmm cache stats

Show cache statistics.

### Usage

```bash
jmm cache stats
```

### Output

```
Cache Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Location: ~/.jackmediaman/cache/

Metadata Cache (FFprobe results):
  File:     metadata.db
  Size:     2.4 MB
  Entries:  1,245
  TTL:      24 hours
  Oldest:   2024-01-10 14:32:00
  Newest:   2024-01-15 09:45:00

TMDb Cache (API responses):
  File:     tmdb.db
  Size:     8.1 MB
  Entries:  3,892
  Movies:   2,104
  TV Shows: 1,788

Total cache size: 10.5 MB
```

---

## jmm cache clear

Clear cache entries.

### Usage

```bash
jmm cache clear [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type`, `-t` | `all` | Which cache: `all`, `metadata`, or `tmdb` |
| `--yes`, `-y` | false | Skip confirmation |

### Examples

```bash
# Clear all caches (with confirmation)
jmm cache clear

# Clear without confirmation
jmm cache clear --yes

# Clear only metadata cache
jmm cache clear --type metadata

# Clear only TMDb cache
jmm cache clear --type tmdb --yes
```

### Output

```
Clearing cache...

Cache to clear: all
  Metadata: 1,245 entries (2.4 MB)
  TMDb:     3,892 entries (8.1 MB)

Are you sure? [y/N]: y

✓ Cleared metadata cache: 1,245 entries
✓ Cleared TMDb cache: 3,892 entries

Freed 10.5 MB
```

---

## jmm cache cleanup

Remove stale (expired) cache entries.

### Usage

```bash
jmm cache cleanup
```

### Output

```
Cache Cleanup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Checking for stale entries...

Metadata Cache:
  Total:     1,245
  Expired:   89
  Removed:   89

TMDb Cache:
  Total:     3,892
  Orphaned:  12
  Removed:   12

Freed: 1.2 MB
```

Cleanup removes:
- Metadata entries older than TTL
- TMDb entries for deleted files
- Corrupted entries

---

## Cache Types

### Metadata Cache

**Location:** `~/.jackmediaman/cache/metadata.db`

Stores FFprobe results:
- Video resolution
- Codec information
- Duration
- File size

**TTL:** Configurable (default 24 hours)

**When to clear:**
- After re-encoding files
- If quality detection seems wrong
- After updating FFprobe

### TMDb Cache

**Location:** `~/.jackmediaman/cache/tmdb.db`

Stores API responses:
- Movie searches
- TV show searches
- Episode details
- Movie details

**TTL:** No automatic expiry

**When to clear:**
- If TMDb data seems outdated
- After TMDb updates their database
- If matching is returning wrong results

---

## Configuration

Cache settings in `~/.jackmediaman.env`:

```env
# Cache location
JMM_CACHE_DIR=~/.jackmediaman/cache

# Metadata cache TTL (seconds)
JMM_CACHE_TTL=86400  # 24 hours
```

---

## When to Clear Cache

### Clear Metadata Cache

- You re-encoded files
- FFprobe was updated
- Quality detection is wrong
- Files were modified

### Clear TMDb Cache

- Show/movie metadata is outdated
- TMDb matching returns wrong results
- You want fresh data

### Clear All

- Starting fresh
- Troubleshooting issues
- Disk space is low

---

## Cache Benefits

| Without Cache | With Cache |
|--------------|------------|
| FFprobe runs on every scan | FFprobe runs once per file |
| TMDb API call per lookup | API call only for new items |
| Slow for large libraries | Fast repeat operations |
| May hit API rate limits | Minimal API usage |

---

## Related Pages

- [Configuration](Configuration) - Cache settings
- [Quality Scoring](Quality-Scoring) - Uses metadata cache
- [Setup TMDb](Setup-TMDb) - Uses TMDb cache
