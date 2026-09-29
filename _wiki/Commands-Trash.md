# jmm trash

Manage the trash directory.

## Overview

When JackMediaMan removes duplicate files, they're moved to trash rather than permanently deleted. The trash command lets you view, restore, and empty the trash.

## Subcommands

| Command | Description |
|---------|-------------|
| `jmm trash list` | List contents of trash |
| `jmm trash clear` | Permanently delete files |
| `jmm trash restore` | Restore a file from trash |

---

## jmm trash list

List all files in the trash directory.

### Usage

```bash
jmm trash list
```

### Output

```
Trash Contents
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#   Date         Size    Name
──────────────────────────────────────────────────────────
1   2024-01-15   4.2 GB  The.Matrix.1999.720p.HDTV.mkv
2   2024-01-15   1.1 GB  Breaking.Bad.S01E01.480p.mkv
3   2024-01-14   2.8 GB  Movie.2023.DVDRip.avi
4   2024-01-12   890 MB  Show.S02E05.WEBRip.mp4
5   2024-01-10   1.5 GB  Another.Movie.2022.mkv
──────────────────────────────────────────────────────────
Total: 5 files, 10.5 GB

Commands:
  jmm trash restore <#>  - Restore a file
  jmm trash clear        - Empty trash
```

Files are numbered for easy reference with `restore`.

---

## jmm trash clear

Permanently delete files from trash.

### Usage

```bash
jmm trash clear [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--days`, `-d` | (all) | Only delete files older than N days |
| `--yes`, `-y` | false | Skip confirmation |

### Examples

```bash
# Empty all trash (with confirmation)
jmm trash clear

# Empty without confirmation
jmm trash clear --yes

# Only delete files older than 30 days
jmm trash clear --days 30

# Combine options
jmm trash clear -d 7 -y
```

### Output

```
Clearing trash...

Files to delete:
  The.Matrix.1999.720p.HDTV.mkv     (4.2 GB) - 5 days old
  Breaking.Bad.S01E01.480p.mkv      (1.1 GB) - 5 days old
  Movie.2023.DVDRip.avi             (2.8 GB) - 6 days old
  Show.S02E05.WEBRip.mp4            (890 MB) - 8 days old
  Another.Movie.2022.mkv            (1.5 GB) - 10 days old

Total: 5 files, 10.5 GB

Delete permanently? This cannot be undone. [y/N]: y

✓ Deleted 5 files
✓ Freed 10.5 GB
```

---

## jmm trash restore

Restore a file from trash to its original location.

### Usage

```bash
jmm trash restore <NUMBER>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `number` | Yes | File number from `jmm trash list` |

### Examples

```bash
# List trash first
jmm trash list

# Restore file #1
jmm trash restore 1

# Restore file #3
jmm trash restore 3
```

### Output

```
Restoring file #1...

File: The.Matrix.1999.720p.HDTV.mkv
Size: 4.2 GB
Original location: /media/Movies/The Matrix (1999)/

✓ Restored successfully

Note: If a higher-quality version exists at this location,
you may want to run 'jmm duplicates scan' again.
```

---

## Trash Location

Default: `~/.jackmediaman/trash/`

Configure in `~/.jackmediaman.env`:
```env
JMM_TRASH_DIR=/path/to/custom/trash
```

---

## File Organization in Trash

Files are renamed with timestamp prefix for uniqueness:

```
~/.jackmediaman/trash/
├── 20240115_143022_The.Matrix.1999.720p.HDTV.mkv
├── 20240115_143025_Breaking.Bad.S01E01.480p.mkv
├── 20240114_091532_Movie.2023.DVDRip.avi
└── ...
```

Original path is stored in metadata for restore.

---

## Automatic Trash Management

You can set up periodic cleanup:

```bash
# Add to crontab: delete files older than 30 days
0 0 * * * /usr/local/bin/jmm trash clear --days 30 --yes
```

Or manually clear periodically:
```bash
jmm trash clear --days 30
```

---

## Safety Features

- **Not permanent:** Files go to trash, not `/dev/null`
- **Restore available:** Can recover files if needed
- **Confirmation:** Clear asks for confirmation (unless `--yes`)
- **Age filtering:** Can clear only old files

---

## Disk Space

Check trash size:
```bash
jmm trash list
```

The total size is shown at the bottom.

If disk space is low:
```bash
# Clear all trash immediately
jmm trash clear --yes
```

---

## Related Pages

- [Commands: duplicates](Commands-Duplicates) - Sends files to trash
- [Commands: status](Commands-Status) - `jmm status trash` shortcut
- [Configuration](Configuration) - Trash directory setting
