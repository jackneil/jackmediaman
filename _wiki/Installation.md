# Installation

This guide covers installing JackMediaMan and its dependencies.

## Requirements

- **Python 3.10+** (3.10, 3.11, or 3.12)
- **pip** or **uv** package manager
- **FFprobe** (optional, for accurate quality detection)

---

## Quick Install

### From PyPI (Recommended)

```bash
pip install --user jackmediaman
~/.local/bin/jmm setup shell   # Configure PATH (one-time)
source ~/.bashrc               # Or start new terminal
jmm --version
```

### From GitHub (Latest)

```bash
pip install --user git+https://github.com/jackneil/jackmediaman.git
~/.local/bin/jmm setup shell
source ~/.bashrc
```

### From Source

```bash
git clone https://github.com/jackneil/jackmediaman.git
cd jackmediaman
pip install --user -e .
~/.local/bin/jmm setup shell
source ~/.bashrc
```

### Verify Installation

```bash
jmm --version
```

Should output: `JackMediaMan v0.3.0`

---

## Seedbox Installation (No Root Required)

For shared seedboxes (Bytesized, Feral, Whatbox, etc.) where you don't have root access:

### Quick Install

```bash
# Install
pip install --user jackmediaman

# Auto-configure shell PATH
~/.local/bin/jmm setup shell
source ~/.bashrc

# Verify
jmm --version
```

### What `jmm setup shell` Does

The command automatically:
1. Detects your shell (bash, zsh, fish)
2. Adds `~/.local/bin` to your PATH
3. Updates the appropriate rc file (.bashrc, .zshrc, etc.)

Use `--dry-run` to preview changes without modifying files:
```bash
~/.local/bin/jmm setup shell --dry-run
```

### Alternative: Virtual Environment

If you prefer isolation:

```bash
python3 -m venv ~/jmm-venv
source ~/jmm-venv/bin/activate
pip install jackmediaman
jmm --version
```

Add to `~/.bashrc` for persistence:
```bash
alias jmm="~/jmm-venv/bin/jmm"
```

### From GitHub (if PyPI blocked)

Some seedbox providers block PyPI. Use GitHub directly:

```bash
pip install --user git+https://github.com/jackneil/jackmediaman.git
~/.local/bin/jmm setup shell
source ~/.bashrc
```

---

## Installation Options

### Basic Installation

Core functionality only:

```bash
pip install -e .
```

### With Development Tools

For contributing or running tests:

```bash
pip install -e ".[dev]"
```

Includes: pytest, mypy, ruff

### With Archive Support

For extracting RAR and 7z archives:

```bash
pip install -e ".[archives]"
```

Includes: rarfile, py7zr

### With REST API Server

For the FastAPI web backend:

```bash
pip install -e ".[web]"
```

Includes: FastAPI, Uvicorn, websockets

### Full Installation

All optional dependencies:

```bash
pip install -e ".[dev,archives,web]"
```

---

## System Dependencies

### FFprobe (Optional but Recommended)

FFprobe enables accurate video quality detection (resolution, codec, HDR).

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
```bash
choco install ffmpeg
# Or download from https://ffmpeg.org/download.html
```

**Verify:**
```bash
ffprobe -version
```

JackMediaMan works without FFprobe but falls back to filename-based quality detection.

### UnRAR (For Archive Extraction)

If processing torrents with RAR archives:

**Ubuntu/Debian:**
```bash
sudo apt install unrar
```

**macOS:**
```bash
brew install unrar
```

**Windows:**
Download from [rarlab.com](https://www.rarlab.com/rar_add.htm)

---

## Virtual Environment Setup

Recommended for isolated installation:

```bash
# Create virtual environment
python3 -m venv ~/.venvs/jmm

# Activate it
source ~/.venvs/jmm/bin/activate

# Install JackMediaMan
cd /path/to/jackmediaman
pip install -e .
```

### Making `jmm` Available System-Wide

**Option 1: Add venv bin to PATH**

Add to `~/.bashrc` or `~/.zshrc`:
```bash
export PATH="$HOME/.venvs/jmm/bin:$PATH"
```

**Option 2: Create alias**

```bash
alias jmm="$HOME/.venvs/jmm/bin/jmm"
```

**Option 3: Symlink**

```bash
sudo ln -s ~/.venvs/jmm/bin/jmm /usr/local/bin/jmm
```

---

## Configuration

After installation, create your configuration file:

```bash
# Copy the example
cp .env.example ~/.jackmediaman.env

# Edit with your paths
nano ~/.jackmediaman.env
```

Minimum required configuration:

```env
# Your media library paths
JMM_TV_DIR=/path/to/TV Shows
JMM_MOVIES_DIR=/path/to/Movies

# Where completed torrents are
JMM_TORRENT_DIR=/path/to/torrents/completed
```

See [Configuration](Configuration) for all options.

---

## Post-Installation Setup

### 1. Verify Configuration

```bash
jmm status config
```

### 2. Set Up Services (Optional)

```bash
# TMDb (for accurate matching and artwork)
jmm setup tmdb

# OpenSubtitles (for subtitle downloads)
jmm setup opensubtitles

# Deluge (for torrent protection)
jmm setup deluge
```

### 3. Test with Dry Run

```bash
# Scan for duplicates without making changes
jmm duplicates scan --type both
```

---

## Updating

```bash
cd /path/to/jackmediaman
git pull
pip install -e .
```

---

## Uninstalling

```bash
pip uninstall jackmediaman
```

Remove configuration:
```bash
rm ~/.jackmediaman.env
rm -rf ~/.jackmediaman/
```

---

## Troubleshooting

### Command Not Found

If `jmm` command isn't found after installation:

1. Check pip installed to correct location:
   ```bash
   pip show jackmediaman
   ```

2. Find where scripts are installed:
   ```bash
   python -m site --user-base
   ```

3. Add bin directory to PATH:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

### Permission Denied

If you get permission errors:

1. Don't use `sudo pip install`
2. Use a virtual environment instead
3. Or install with `--user` flag:
   ```bash
   pip install --user -e .
   ```

### Python Version Issues

Check your Python version:
```bash
python3 --version
```

JackMediaMan requires Python 3.10 or newer. If you have an older version:

**Ubuntu/Debian:**
```bash
sudo apt install python3.11
```

**macOS:**
```bash
brew install python@3.11
```

---

## Next Steps

1. [Configuration](Configuration) - Set up your library paths
2. [Setup Guides](Setup-TMDb) - Configure external services
3. [Commands](Commands) - Learn available commands
