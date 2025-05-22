#!/bin/bash

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install global tools
uv tool install nox
uv tool install pre-commit

# Dry-run precommit on a single file (forces deps to be installed)
pre-commit run --hook-stage pre-push --files ./weave/__init__.py

# Install the env test shards
nox --install-only -e "tests-3.12(shard='custom')"
nox --install-only -e "tests-3.12(shard='trace')"
nox --install-only -e "tests-3.12(shard='flow')"
nox --install-only -e "tests-3.12(shard='trace_server')"
nox --install-only -e "tests-3.12(shard='trace_server_bindings')"


# Run a lint dry-run to install deps
nox -e lint -- dry-run

