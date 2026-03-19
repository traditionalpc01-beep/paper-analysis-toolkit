import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_agent_harness_check_script_passes():
    result = subprocess.run(
        [sys.executable, "scripts/check_agent_harness.py", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert any(check["name"] == "report columns" for check in payload["checks"])
