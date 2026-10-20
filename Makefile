.PHONY: build

build:
	uv build

prerelease-dry-run:
	uv run ./scripts/prerelease_dry_run.py

prepare-release: build
