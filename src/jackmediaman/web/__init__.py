"""JackMediaMan Web API.

FastAPI-based REST API for the web interface.
"""

from .main import app, start_server

__all__ = ["app", "start_server"]
