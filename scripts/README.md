# Scripts

This directory contains scripts for the weave repo, including:

1. `benchmark.py` -- a CLI for running benchmarks from the `benchmarks/` directory
2. `strip_exif.py` -- a script for stripping EXIF data from images (used as a pre-commit hook)

## 1. Benchmarking

To run a benchmark, invoke `uv run benchmark.py`. This will bring up a CLI for selecting and running benchmarks from the `benchmarks/` directory. If you want to run a specific benchmark, you can do `uv run benchmark.py run <benchmark_name>`.

## 2. Stripping EXIF data from images

To run the pre-commit hook, invoke `nox -e lint`.
