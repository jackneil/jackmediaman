# jmm torrents

Manage Deluge torrents.

## Overview

The torrents command provides a convenient way to view and manage your Deluge torrents from the command line.

## Subcommands

| Command | Description |
|---------|-------------|
| `jmm torrents list` | List all torrents with status |
| `jmm torrents move` | Move completed torrents to completed folder |

---

## jmm torrents list

List all torrents with their status.

### Usage

```bash
jmm torrents list
```

### Output

```
Deluge Torrents (146 total)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Name                                    Progress  State      Size     Location
────────────────────────────────────────────────────────────────────────────
The.Matrix.1999.1080p.BluRay            100.0%    Seeding    15.2 GB  /completed
Breaking.Bad.S01E01.720p                100.0%    Seeding    1.1 GB   /completed
Some.Movie.2024.WEB-DL                  45.2%     Download   4.5 GB   /downloading
Another.Show.S02E05                     0.0%      Queued     890 MB   /downloading
Failed.Download                         78.3%     Error      2.1 GB   /downloading
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### State Colors

| State | Color | Meaning |
|-------|-------|---------|
| Seeding | Green | Completed, uploading to peers |
| Downloading | Blue | Actively downloading |
| Paused | Yellow | Paused by user |
| Queued | Yellow | Waiting in queue |
| Error | Red | Download failed |
| Checking | Cyan | Verifying files |

---

## jmm torrents move

Move completed torrents to the completed folder.

### Usage

```bash
jmm torrents move [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | (default) | Preview what would be moved |
| `--execute` | | Actually move the torrents |

### Examples

```bash
# Preview what would be moved
jmm torrents move

# Execute the move
jmm torrents move --execute
```

### Output (Dry Run)

```
Torrents to move: 5

  The.Matrix.1999.1080p.BluRay
    From: /downloads/downloading
    To:   /downloads/completed

  Breaking.Bad.S01E01.720p
    From: /downloads/downloading
    To:   /downloads/completed

  ...

Use --execute to perform the move.
```

### Output (Execute)

```
Moving torrents...

✓ The.Matrix.1999.1080p.BluRay
  Moved to: /downloads/completed

✓ Breaking.Bad.S01E01.720p
  Moved to: /downloads/completed

Summary: 5/5 torrents moved successfully
```

---

## Use Case

The move command is useful when:

1. You enabled "Move completed downloads" in Deluge **after** some torrents already finished
2. Those completed torrents are still in the downloading folder
3. You want to move them to the completed folder while preserving seeding

This allows you to organize existing torrents without:
- Removing and re-adding them
- Losing seeding history
- Breaking the torrent

---

## Configuration

Requires Deluge daemon credentials:

```env
JMM_DELUGE_HOST=127.0.0.1
JMM_DELUGE_PORT=58846
JMM_DELUGE_USERNAME=localclient
JMM_DELUGE_PASSWORD=your_password
```

Configure: `jmm setup deluge`

Also uses:
```env
JMM_TORRENT_DIR=/path/to/completed
```

---

## How Move Works

When you run `jmm torrents move --execute`:

1. Connects to Deluge daemon
2. Finds torrents that are:
   - 100% complete
   - Not already in completed directory
3. Uses Deluge's `move_storage` API to relocate files
4. Seeding continues from new location

This is different from manually moving files, which would break the torrent.

---

## Troubleshooting

### Connection Failed

```
Error: Could not connect to Deluge daemon
```

- Check deluged is running: `pgrep deluged`
- Verify host/port: `jmm status deluge`
- Check credentials in config

### Authentication Failed

```
Error: Authentication failed
```

- Verify username/password in config
- Check `~/.config/deluge/auth` file
- Run `jmm setup deluge` to reconfigure

### Move Failed

```
Error: Failed to move torrent
```

Possible causes:
- Destination directory doesn't exist
- Permission denied on destination
- Disk full

Check Deluge logs for details.

---

## Related Pages

- [Setup Deluge](Setup-Deluge) - Configuration guide
- [Commands: status](Commands-Status) - Check Deluge connection
- [Configuration](Configuration) - Deluge settings
