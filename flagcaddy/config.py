"""Configuration management for FlagCaddy."""

import os
from pathlib import Path

# Base directory for FlagCaddy data
FLAGCADDY_DIR = Path.home() / ".flagcaddy"
FLAGCADDY_DIR.mkdir(exist_ok=True)

# Database path
DB_PATH = FLAGCADDY_DIR / "flagcaddy.db"

# Terminal capture settings
CAPTURE_LOG_PATH = FLAGCADDY_DIR / "terminal_capture.log"

# Web UI settings
WEB_HOST = os.getenv("FLAGCADDY_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("FLAGCADDY_PORT", "5000"))

# Analysis settings
ANALYSIS_INTERVAL = int(os.getenv("FLAGCADDY_ANALYSIS_INTERVAL", "30"))  # seconds
CODEX_EXEC_PATH = os.getenv("FLAGCADDY_CODEX_EXEC", "codex")

# Organization patterns
IP_PATTERN = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
DOMAIN_PATTERN = r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b'
PORT_PATTERN = r'\b(?:port[s]?\s+)?(\d{1,5})(?:/tcp|/udp)?\b'
