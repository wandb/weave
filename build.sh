#!/usr/bin/env bash

set -e

rm -rf dist
bash weave/frontend/build.sh
python -m build
echo "Push to pypi with: python -m twine upload --repository pypi dist/*"