from pathlib import Path


def test_import_not_slow(monkeypatch):
    root_dir = Path.cwd().parent.parent  # root dir of repo
    monkeypatch.setenv("PYTHONPATH", str(root_dir))

    from scripts.benchmark_import import run_single_import

    import_time = run_single_import()
    assert import_time < 2, f"Import time was {import_time} seconds"
