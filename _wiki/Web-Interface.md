# REST API

JackMediaMan includes a FastAPI backend that provides a REST API for automation, scripting, and integration with other tools.

## Starting the API Server

```bash
# Start on default port (8080)
jmm --web

# Start on a custom port
jmm --web --port 9000
```

The API will be available at `http://localhost:8080` (or your custom port).

## Requirements

The REST API requires the optional `web` dependencies:

```bash
pip install jackmediaman[web]
```

This installs:
- FastAPI - Modern web framework
- Uvicorn - ASGI server
- websockets - For future real-time features

## API Endpoints

### Health & Status

#### `GET /api/health`
Simple health check endpoint.

```bash
curl http://localhost:8080/api/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

#### `GET /api/status`
Comprehensive status including service connectivity and library stats.

```bash
curl http://localhost:8080/api/status
```

Response:
```json
{
  "services": {
    "tmdb": {"configured": true, "connected": true},
    "deluge": {"configured": true, "connected": false},
    "opensubtitles": {"configured": false, "connected": false}
  },
  "paths": {
    "tv_dir": "/media/TV Shows",
    "movies_dir": "/media/Movies",
    "tv_exists": true,
    "movies_exists": true
  },
  "library": {
    "movie_count": 150,
    "tv_show_count": 45,
    "episode_count": 1200
  }
}
```

#### `POST /api/services/{service}/test`
Test connection to a specific service (tmdb, deluge, opensubtitles).

```bash
curl -X POST http://localhost:8080/api/services/deluge/test
```

---

### Commands

#### `GET /api/commands`
List all available commands.

```bash
curl http://localhost:8080/api/commands
```

Response:
```json
{
  "commands": [
    {"name": "duplicates", "description": "Find and clean duplicate media files"},
    {"name": "process", "description": "Process completed torrent downloads"},
    {"name": "rename", "description": "Rename media files to standard format"},
    ...
  ]
}
```

#### `POST /api/commands/{name}/execute`
Execute a command asynchronously.

```bash
curl -X POST http://localhost:8080/api/commands/duplicates/execute \
  -H "Content-Type: application/json" \
  -d '{"args": ["scan"], "options": {"dry_run": true}}'
```

Response:
```json
{
  "job_id": "abc123",
  "status": "started",
  "command": "duplicates",
  "args": ["scan"]
}
```

#### `GET /api/jobs/{job_id}`
Check status of an async job.

```bash
curl http://localhost:8080/api/jobs/abc123
```

---

### Settings

#### `GET /api/settings`
Get all current settings.

```bash
curl http://localhost:8080/api/settings
```

Response:
```json
{
  "paths": {
    "tv_dir": "/media/TV Shows",
    "movies_dir": "/media/Movies",
    "trash_dir": "~/.local/share/jackmediaman/trash"
  },
  "services": {
    "tmdb_api_key": "abc***",
    "deluge_host": "127.0.0.1",
    "deluge_port": 58846
  },
  ...
}
```

#### `PUT /api/settings`
Update settings.

```bash
curl -X PUT http://localhost:8080/api/settings \
  -H "Content-Type: application/json" \
  -d '{"tv_dir": "/new/path/TV Shows"}'
```

---

## Running as a Service

To keep the API server running in the background:

```bash
# Using screen
screen -S jmm
jmm --web
# Press Ctrl+A, D to detach

# Using tmux
tmux new -s jmm
jmm --web
# Press Ctrl+B, D to detach

# Using nohup
nohup jmm --web > /dev/null 2>&1 &
```

## Remote Access

By default, the API binds to `0.0.0.0`, making it accessible from other devices on your network. Access via `http://your-server-ip:8080`.

> **Security Note:** The API has no authentication. Only expose it on trusted networks or use a reverse proxy with authentication.

---

## OpenAPI Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`

These provide interactive interfaces to explore and test all endpoints.

---

## Troubleshooting

### "Web dependencies not installed" Error

Install the web dependencies:
```bash
pip install jackmediaman[web]
```

### Port Already in Use

Specify a different port:
```bash
jmm --web --port 9000
```

### Connection Refused

Ensure the server is running and check the port:
```bash
curl http://localhost:8080/api/health
```

### CORS Issues

The API includes CORS headers for `localhost` origins. For production use with a frontend, you may need to configure additional origins.
