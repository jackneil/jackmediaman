# Deluge Setup Guide

This guide covers setting up Deluge integration with JackMediaMan for seeding protection and torrent management.

## Overview

JackMediaMan integrates with Deluge to:

- **Protect seeding files** - Prevent deletion of files that are actively seeding
- **Manage torrents** - List torrents and move completed downloads
- **Automate processing** - Trigger `jmm process` when torrents complete (via Execute plugin)

## When Do You Need This?

- If you use Deluge as your torrent client
- If you want to protect seeding files during duplicate cleanup
- If you want to use `jmm torrents` commands
- If you want automatic processing when torrents complete

If you don't use Deluge, you can skip this guide and use symlink-based protection instead.

---

## Part 1: Deluge Daemon Setup

JackMediaMan connects to the Deluge daemon (`deluged`), not the GTK or web UI.

### Installing Deluge

**Ubuntu/Debian:**
```bash
sudo apt install deluged deluge-console
```

**Arch Linux:**
```bash
sudo pacman -S deluge
```

**macOS (Homebrew):**
```bash
brew install deluge
```

**Docker:**
```bash
docker pull linuxserver/deluge
```

### Starting the Daemon

**Manual start:**
```bash
deluged
```

**As a systemd service:**
```bash
# Create service file
sudo nano /etc/systemd/system/deluged.service
```

```ini
[Unit]
Description=Deluge Bittorrent Client Daemon
After=network-online.target

[Service]
Type=simple
User=your_username
ExecStart=/usr/bin/deluged -d
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable deluged
sudo systemctl start deluged
```

### Default Ports

| Port | Purpose |
|------|---------|
| 58846 | Daemon RPC (default) |
| 8112 | Web UI (if installed) |
| 6881 | BitTorrent incoming |

---

## Part 2: Authentication

### Local Connections (No Auth Required)

**If JackMediaMan and Deluge run on the same machine**, you typically don't need to configure username/password. Deluge allows unauthenticated connections from localhost by default.

**Minimal local configuration:**
```env
JMM_DELUGE_HOST=127.0.0.1
JMM_DELUGE_PORT=58846
# Username and password can be left empty for localhost
JMM_DELUGE_USERNAME=
JMM_DELUGE_PASSWORD=
```

This works because Deluge trusts connections from `127.0.0.1` without authentication.

### Remote Connections (Auth Required)

If connecting from a different machine, you need credentials.

#### The Auth File

Location: `~/.config/deluge/auth`

Format: `username:password:level`

**Access levels:**
- `5` - Admin (read-only)
- `10` - Normal (full access)

#### Creating Credentials

**Option 1: Use existing localclient**

The auth file already contains a `localclient` entry. Get the password:
```bash
cat ~/.config/deluge/auth | grep localclient
```

Output: `localclient:RANDOM_PASSWORD:10`

**Option 2: Create new user**

```bash
echo "jmm:your_secure_password:10" >> ~/.config/deluge/auth
```

Then restart deluged:
```bash
# If using systemd
sudo systemctl restart deluged

# If manual
pkill deluged && deluged
```

#### Allowing Remote Connections

If JackMediaMan runs on a different machine than Deluge:

1. Edit Deluge config:
```bash
nano ~/.config/deluge/core.conf
```

2. Find and change:
```json
"allow_remote": true,
```

3. Restart deluged

---

## Part 3: Common Setup Scenarios

### Scenario 1: Local Installation (Same Machine)

The simplest setup - JackMediaMan and Deluge on the same machine. **No authentication needed.**

**Configuration:**
```env
JMM_DELUGE_HOST=127.0.0.1
JMM_DELUGE_PORT=58846
# Leave empty for local connections
JMM_DELUGE_USERNAME=
JMM_DELUGE_PASSWORD=
```

That's it! For localhost, Deluge accepts connections without credentials.

### Scenario 2: Seedbox (Remote Server)

JackMediaMan on your local machine, Deluge on a remote seedbox.

**Option A: Direct connection (if port is open)**
```env
JMM_DELUGE_HOST=your-seedbox.com
JMM_DELUGE_PORT=58846
JMM_DELUGE_USERNAME=jmm
JMM_DELUGE_PASSWORD=your_password
```

**Option B: SSH tunnel (more secure)**

Create the tunnel:
```bash
ssh -L 58846:localhost:58846 user@your-seedbox.com -N
```

Then configure as local:
```env
JMM_DELUGE_HOST=127.0.0.1
JMM_DELUGE_PORT=58846
JMM_DELUGE_USERNAME=localclient
JMM_DELUGE_PASSWORD=<password>
```

### Scenario 3: Docker Setup

Using `linuxserver/deluge`:

**docker-compose.yml:**
```yaml
version: "3"
services:
  deluge:
    image: lscr.io/linuxserver/deluge:latest
    container_name: deluge
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
      - DELUGE_LOGLEVEL=error
    volumes:
      - /path/to/config:/config
      - /path/to/downloads:/downloads
    ports:
      - 8112:8112
      - 58846:58846
      - 6881:6881
      - 6881:6881/udp
    restart: unless-stopped
```

**Configuration:**
```env
JMM_DELUGE_HOST=localhost
JMM_DELUGE_PORT=58846
JMM_DELUGE_USERNAME=localclient
JMM_DELUGE_PASSWORD=<from /path/to/config/auth>
```

---

## Part 4: JackMediaMan Configuration

Add these to `~/.jackmediaman.env`:

**For local connections (same machine):**
```env
# Deluge Daemon Connection - Local
JMM_DELUGE_HOST=127.0.0.1
JMM_DELUGE_PORT=58846
# No auth needed for localhost - leave empty
JMM_DELUGE_USERNAME=
JMM_DELUGE_PASSWORD=
```

**For remote connections:**
```env
# Deluge Daemon Connection - Remote
JMM_DELUGE_HOST=your-server.com
JMM_DELUGE_PORT=58846
JMM_DELUGE_USERNAME=your_username
JMM_DELUGE_PASSWORD=your_password
```

Or configure interactively:
```bash
jmm setup deluge
```

---

## Part 5: Testing the Connection

```bash
jmm status deluge
```

**Successful output:**
```
Deluge Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Host:       127.0.0.1:58846
Status:     ✓ Connected
Version:    2.1.1
Torrents:   42 total
```

**If it fails, see [Troubleshooting](#troubleshooting) below.**

---

## Part 6: Using Deluge Protection

### In Duplicate Cleanup

Protect seeding files when cleaning duplicates:

```bash
# Use Deluge protection
jmm duplicates scan --protector deluge

# Use both symlink and Deluge protection
jmm duplicates scan --protector both
```

### Listing Torrents

```bash
jmm torrents list
```

Shows all torrents with status, progress, and location.

### Moving Completed Torrents

If you have torrents that completed before enabling "Move completed to":

```bash
# Preview what would be moved
jmm torrents move

# Execute the move
jmm torrents move --execute
```

---

## Part 7: Execute Plugin (Automation)

The Execute plugin can automatically run `jmm process` when torrents complete.

### Installing the Execute Plugin

1. Open Deluge (GTK or Web UI)
2. Go to Preferences > Plugins
3. Enable "Execute"

### Configuring the Hook

1. Go to Preferences > Execute
2. Add a new event:
   - **Event:** Torrent Complete
   - **Command:** `/path/to/jmm-hook.sh`

### Creating the Hook Script

Create `/home/your_user/bin/jmm-hook.sh`:

```bash
#!/bin/bash
# JMM Deluge Execute Hook
# Arguments: torrent_id torrent_name torrent_path

TORRENT_ID="$1"
TORRENT_NAME="$2"
TORRENT_PATH="$3"

# Log file
LOG="/home/your_user/.jackmediaman/hook.log"

echo "$(date): Processing $TORRENT_NAME" >> "$LOG"

# Run JMM process
/home/your_user/.local/bin/jmm process run "$TORRENT_PATH/$TORRENT_NAME" \
    --action keeplink \
    >> "$LOG" 2>&1

echo "$(date): Completed $TORRENT_NAME" >> "$LOG"
```

Make it executable:
```bash
chmod +x /home/your_user/bin/jmm-hook.sh
```

### Hook Options

Customize the `--action` based on your needs:

| Action | Use Case |
|--------|----------|
| `symlink` | Keep original for seeding, create symlink in library |
| `keeplink` | Move to library, leave symlink in download dir for seeding |
| `hardlink` | Create hardlink (same filesystem only) |
| `move` | Move file, stop seeding |
| `copy` | Copy file, keep seeding (uses 2x disk space) |

---

## Troubleshooting

### Connection Refused

**Symptoms:** `Connection refused` or `Cannot connect to daemon`

**Solutions:**
1. Check deluged is running:
   ```bash
   pgrep -a deluged
   ```
2. Check the port is listening:
   ```bash
   netstat -tlnp | grep 58846
   ```
3. Check firewall allows the port:
   ```bash
   sudo ufw status
   ```

### Authentication Failed

**Symptoms:** `Authentication failed` or `Bad login`

**Solutions:**
1. Verify credentials in auth file:
   ```bash
   cat ~/.config/deluge/auth
   ```
2. Make sure password has no special characters that need escaping
3. Try creating a new user with simple password
4. Restart deluged after changing auth

### SSL/TLS Errors

**Symptoms:** `SSL handshake failed` or certificate errors

**Solutions:**
1. Deluge uses SSL by default. Ensure your client supports it
2. Check SSL certificate exists:
   ```bash
   ls ~/.config/deluge/ssl/
   ```
3. If using SSH tunnel, connect to localhost (bypasses SSL issues)

### Wrong Port

**Symptoms:** Connection timeout

**Solutions:**
1. Check core.conf for actual daemon port:
   ```bash
   grep daemon_port ~/.config/deluge/core.conf
   ```
2. Some seedbox providers use non-standard ports (like 4382)

### Docker-Specific Issues

**Symptoms:** Works from inside container, not from host

**Solutions:**
1. Ensure port 58846 is mapped in docker-compose.yml
2. Use `host.docker.internal` if JMM runs in different container
3. Check container logs:
   ```bash
   docker logs deluge
   ```

---

## Quick Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `JMM_DELUGE_HOST` | 127.0.0.1 | Deluge daemon host |
| `JMM_DELUGE_PORT` | 58846 | Deluge daemon port |
| `JMM_DELUGE_USERNAME` | (empty) | Auth username (not needed for localhost) |
| `JMM_DELUGE_PASSWORD` | (empty) | Auth password (not needed for localhost) |

**Note:** For local connections (127.0.0.1/localhost), username and password can be left empty. Authentication is only required for remote connections.

## Related Pages

- [Configuration](Configuration) - All configuration options
- [Commands: torrents](Commands-Torrents) - Torrent management commands
- [Commands: duplicates](Commands-Duplicates) - Duplicate cleanup with protection
- [Commands: process](Commands-Process) - Processing pipeline
