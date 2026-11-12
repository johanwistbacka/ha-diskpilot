"""The disposable lab must not auto-revert its loopback HTTP configuration."""

import json
import subprocess
import sys
from pathlib import Path


def test_fresh_local_http_config_is_stable_loopback_only(tmp_path):
    script = Path(__file__).resolve().parents[1] / "dev" / "prepare_local.py"
    subprocess.run([sys.executable, str(script), str(tmp_path)], check=True, capture_output=True)
    target = tmp_path / ".storage" / "http"
    document = json.loads(target.read_text())
    assert document["data"]["stable"]["server_host"] == ["127.0.0.1"]
    assert document["data"]["stable"]["server_port"] == 8124
    assert document["data"]["pending"] is None
    assert target.stat().st_mode & 0o777 == 0o600
    original = target.read_bytes()
    subprocess.run([sys.executable, str(script), str(tmp_path)], check=True, capture_output=True)
    assert target.read_bytes() == original
