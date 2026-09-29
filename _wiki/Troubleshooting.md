# Troubleshooting

Common issues and solutions for JackMediaMan.

## Installation Issues

### Command Not Found

**Problem:** `jmm: command not found` after installation

**Solutions:**

1. Check pip installation location:
   ```bash
   pip show jackmediaman
   ```

2. Add to PATH:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

3. Or use full path:
   ```bash
   ~/.local/bin/jmm --version
   ```

### Python Version Error

**Problem:** `Python 3.10+ required`

**Solution:** Install Python 3.10 or newer:
```bash
# Ubuntu/Debian
sudo apt install python3.11

# macOS
brew install python@3.11
```

### Permission Denied

**Problem:** `Permission denied` during pip install

**Solution:** Don't use `sudo pip`. Use:
```bash
pip install --user -e .
# Or use a virtual environment
python3 -m venv ~/.venvs/jmm
source ~/.venvs/jmm/bin/activate
pip install -e .
```

---

## Connection Issues

### Deluge Connection Refused

**Problem:** `Connection refused - is deluged running?`

**Solutions:**

1. Check if deluged is running:
   ```bash
   pgrep -a deluged
   ```

2. Start it:
   ```bash
   deluged
   ```

3. Check the port:
   ```bash
   netstat -tlnp | grep 58846
   ```

4. Verify config:
   ```bash
   jmm status deluge
   ```

### Deluge Authentication Failed

**Problem:** `Authentication failed` or `Bad login`

**Solutions:**

1. Check auth file:
   ```bash
   cat ~/.config/deluge/auth
   ```

2. Verify credentials match config:
   ```bash
   cat ~/.jackmediaman.env | grep DELUGE
   ```

3. Reconfigure:
   ```bash
   jmm setup deluge
   ```

### TMDb API Error

**Problem:** `401 Unauthorized` from TMDb

**Solutions:**

1. Verify API key:
   ```bash
   jmm status tmdb
   ```

2. Check key is v3 (not v4)

3. Reconfigure:
   ```bash
   jmm setup tmdb
   ```

### OpenSubtitles Rate Limited

**Problem:** `429 Too Many Requests` or `Daily limit reached`

**Solutions:**

1. Check usage:
   ```bash
   jmm subtitles status
   ```

2. Wait until midnight UTC

3. Process fewer files at once

---

## Processing Issues

### Archive Extraction Fails

**Problem:** `RAR extraction requires unrar` or similar

**Solutions:**

Install extraction tools:
```bash
# Ubuntu/Debian
sudo apt install unrar p7zip-full

# macOS
brew install unrar p7zip

# Or install Python packages
pip install rarfile py7zr
```

### Wrong Media Type Detected

**Problem:** Movie detected as TV show (or vice versa)

**Cause:** Filename contains TV-like patterns (S01, E01, etc.)

**Solutions:**

1. Check filename for misleading patterns
2. Rename file before processing
3. Use `--no-tmdb` if TMDb is wrong

### Destination Already Exists

**Problem:** `Destination already exists` error

**Solutions:**

1. Delete existing file
2. Rename existing file
3. Use different action mode
4. Process to different directory

### No Video Files Found

**Problem:** `No video files found`

**Causes:**
- Path doesn't contain video files
- Files have unusual extensions
- All files are sample files

**Solutions:**

1. Check the path contains videos:
   ```bash
   ls -la /path/to/download
   ```

2. Check for sample files (auto-filtered):
   - Files with "sample" in name are skipped

---

## Quality Issues

### Wrong Resolution Detected

**Problem:** File marked as wrong quality (e.g., 720p shows as 1080p)

**Solutions:**

1. Enable FFprobe for accurate detection:
   ```env
   JMM_FFPROBE_ENABLED=true
   ```

2. Clear metadata cache:
   ```bash
   jmm cache clear --type metadata
   ```

3. Check filename doesn't have misleading quality tags

### FFprobe Not Working

**Problem:** `ffprobe: command not found`

**Solutions:**

1. Install FFmpeg:
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg

   # macOS
   brew install ffmpeg
   ```

2. Or disable FFprobe:
   ```env
   JMM_FFPROBE_ENABLED=false
   ```

---

## Duplicate Issues

### No Duplicates Found

**Problem:** Duplicates exist but aren't detected

**Causes:**
- Different parsing of similar filenames
- Files in unexpected locations
- Matcher not matching variations

**Solutions:**

1. Try different matcher:
   ```bash
   jmm duplicates scan --matcher fuzzy
   jmm duplicates scan --matcher tmdb
   ```

2. Check files are in configured directories:
   ```bash
   jmm status config
   ```

### Wrong Files Marked as Duplicates

**Problem:** Different movies/episodes grouped together

**Cause:** Similar titles, wrong year, or TMDb returning wrong match

**Solutions:**

1. Use `--matcher title_year` for strict matching
2. Ensure filenames include year: `Movie (2024)`
3. Check TMDb for ambiguous titles

### Protected Files

**Problem:** Want to remove file but it's marked protected

**Cause:** File is symlinked or actively seeding

**Solutions:**

1. If done seeding, use `--protector none`:
   ```bash
   jmm duplicates clean --protector none
   ```

2. Remove from Deluge first

3. Check symlink status:
   ```bash
   ls -la /path/to/file
   ```

---

## Configuration Issues

### Config Not Loading

**Problem:** Settings don't take effect

**Solutions:**

1. Check file location:
   ```bash
   ls -la ~/.jackmediaman.env
   ```

2. Check syntax (no quotes around values):
   ```env
   # Correct
   JMM_TV_DIR=/media/TV Shows

   # Wrong
   JMM_TV_DIR="/media/TV Shows"
   ```

3. Reload settings:
   ```bash
   jmm status config
   ```

### Paths with Spaces

**Problem:** Paths with spaces not working

**Solutions:**

In config file, don't quote:
```env
JMM_TV_DIR=/media/TV Shows
```

In command line, quote or escape:
```bash
jmm process run "/downloads/Movie Name (2024)"
jmm process run /downloads/Movie\ Name\ \(2024\)
```

---

## Performance Issues

### Slow Scanning

**Problem:** Duplicate scan takes very long

**Solutions:**

1. Use faster matcher:
   ```bash
   jmm duplicates scan --matcher title_year
   ```

2. Reduce FFprobe workers:
   ```env
   JMM_FFPROBE_WORKERS=2
   ```

3. Disable FFprobe:
   ```env
   JMM_FFPROBE_ENABLED=false
   ```

### High Memory Usage

**Problem:** JMM uses too much memory

**Solutions:**

1. Process smaller batches
2. Clear cache:
   ```bash
   jmm cache clear
   ```

---

## Getting Help

### Check Logs

Most errors are displayed in the terminal output. For more detail:

```bash
# Verbose output (if supported)
jmm duplicates scan 2>&1 | tee jmm.log
```

### Verify Configuration

```bash
jmm status config
jmm status deluge
jmm status tmdb
jmm status opensubtitles
```

### Reset to Defaults

```bash
# Clear all caches
jmm cache clear --yes

# Remove config (backup first)
mv ~/.jackmediaman.env ~/.jackmediaman.env.bak

# Reconfigure
jmm setup tmdb
jmm setup deluge
jmm setup opensubtitles
```

### Report Issues

If you can't resolve the issue:

1. Check existing issues: [GitHub Issues](https://github.com/jackneil/jackmediaman/issues)
2. Include:
   - JMM version: `jmm --version`
   - Python version: `python3 --version`
   - Error message
   - Steps to reproduce

---

## Related Pages

- [Installation](Installation) - Setup guide
- [Configuration](Configuration) - All settings
- [Setup Deluge](Setup-Deluge) - Deluge troubleshooting
- [Setup TMDb](Setup-TMDb) - TMDb troubleshooting
- [Setup OpenSubtitles](Setup-OpenSubtitles) - Subtitles troubleshooting
