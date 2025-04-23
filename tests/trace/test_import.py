from pathlib import Path


def test_import_not_slow(monkeypatch):
    root_dir = Path.cwd().parent.parent  # root dir of repo
    monkeypatch.setenv("PYTHONPATH", str(root_dir))

    from scripts.benchmark_import import run_single_import

    import_time = run_single_import()

    # Ideally the import takes < 1s, but in CI it can take up to 5s.
    assert import_time < 5, f"Import time was {import_time} seconds"
