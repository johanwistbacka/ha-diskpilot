"""Seed loopback-only HTTP settings for a fresh, disposable HA 2026.11 lab."""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from homeassistant.components.http.config import HTTP_STORAGE_SCHEMA

root = Path(sys.argv[1])
storage = root / ".storage"
storage.mkdir(mode=0o700, parents=True, exist_ok=True)
target = storage / "http"
if not target.exists():
    settings = dict(HTTP_STORAGE_SCHEMA({"server_host": ["127.0.0.1"], "server_port": 8124}))
    settings.update(created_at=datetime.now(UTC).isoformat(), error=None, error_message=None)
    document = {
        "version": 3,
        "minor_version": 1,
        "key": "http",
        "data": {"stable": settings, "pending": None, "yaml_migration_done": True},
    }
    with target.open("x") as file:
        json.dump(document, file, indent=2)
    os.chmod(target, 0o600)
