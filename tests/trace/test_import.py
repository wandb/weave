from pathlib import Path

from scripts.benchmarks.weave_setup_time import time_weave_import


def test_import_not_slow(monkeypatch):
    """Test that weave import time is within acceptable limits using benchmarking data.

    This test uses the comprehensive benchmarking functions from
    scripts/benchmarks/weave_setup_time.py to measure import performance.
    """
    root_dir = Path.cwd().parent.parent  # root dir of repo
    monkeypatch.setenv("PYTHONPATH", str(root_dir))

    import_time = time_weave_import()

    # Ideally the import takes < 1s, but in CI it can take up to 8s.
    assert import_time < 8, f"Import time was {import_time} seconds"
