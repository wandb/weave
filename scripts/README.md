# Scripts

This directory contains scripts for the weave repo, including:

1. `benchmark.py` -- a CLI for running benchmarks from the `benchmarks/` directory
2. `strip_exif.py` -- a script for stripping EXIF data from images (used as a prek hook)
3. `validate_agent_read_sdk.py` -- a CLI that exercises every agent read SDK method against a running trace server

## 1. Benchmarking

To run a benchmark, invoke `uv run benchmark.py`. This will bring up a CLI for selecting and running benchmarks from the `benchmarks/` directory. If you want to run a specific benchmark, you can do `uv run benchmark.py run <benchmark_name>`.

## 2. Stripping EXIF data from images

To run the prek hook, invoke `nox -e lint`.

## 3. Validating the agent read SDK

Smoke-tests all eight `WeaveClient` agent read methods against a running trace server (e.g. a local Tilt deploy) over real HTTP. Requires `WANDB_API_KEY` and a trace server URL:

```
export WANDB_API_KEY=...
export WF_TRACE_SERVER_URL=https://trace-server.wandb.test
export WEAVE_INSECURE_DISABLE_SSL=true   # only if the server's cert isn't in your trust store
uv run python scripts/validate_agent_read_sdk.py --entity ENTITY --project PROJECT
```
