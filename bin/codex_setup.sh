#!/bin/bash

curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install nox
uv tool install pre-commit
nox --install-only -e lint
nox --install-only -e "tests-3.12(shard='custom')"
nox --install-only -e "tests-3.12(shard='trace')"
nox --install-only -e "tests-3.12(shard='flow')"
nox --install-only -e "tests-3.12(shard='trace_server')"
nox --install-only -e "tests-3.12(shard='trace_server_bindings')"

