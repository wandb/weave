# Weave benchmarks

This directory has self-contained benchmarks for testing Weave performance/overhead.

To run a benchmark, do `uv run <benchmark_name>.py`.

## `import_init_profile.py` — import & init cold-start profiler

Profiles `import weave` (deterministic, the real optimization target) and the
offline code cost of `weave.init()` (the disabled path; real init is
network-bound). It prints cold-import/init timing stats, a per-module
`-X importtime` breakdown (by package and by module), and writes flame-graph
artifacts.

Run it inside the project venv so `import weave` resolves to this checkout
(not a pinned PyPI build):

```bash
source .venv/bin/activate
python scripts/benchmarks/import_init_profile.py            # full run + flame graphs
python scripts/benchmarks/import_init_profile.py --no-flame # timing + breakdown only
python scripts/benchmarks/import_init_profile.py --out-dir /tmp/prof
```

Artifacts land in `.artifacts/` (gitignored):

- `flame_importtime.html` — self-contained import-time flame graph (icicle),
  built from `-X importtime`; faithful, no sampling distortion. Open in a browser.
- `flame_pyinstrument.html` / `.txt` — call-stack flame graph (needs
  `pyinstrument`; shows *what* runs, but its 0.1 ms sampling over-weights
  call-heavy pure-Python code, so trust `importtime` for magnitude).
- `flame_pyspy.svg` — py-spy flame graph (best effort; needs `sudo` on macOS).
- `importtime.log` — raw log; view as an icicle with `tuna .artifacts/importtime.log`.
