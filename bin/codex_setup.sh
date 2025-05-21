#!/bin/bash

curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install nox
uv tool install pre-commit

