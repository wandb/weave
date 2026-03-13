"""CI test: verify serialization fixtures match current to_json output.

If this test fails, serialization behavior has changed. Update the fixtures:
    python scripts/generate_serialization_fixtures.py
"""

from __future__ import annotations

import subprocess
import sys


def test_serialization_fixtures_are_current() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_serialization_fixtures.py", "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Serialization fixtures are stale.\n"
        f"{result.stderr}\n"
        "Run: python scripts/generate_serialization_fixtures.py"
    )
