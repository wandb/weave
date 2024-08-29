#!/bin/bash

# Fix cache perms
mkdir -p $HOME/.cache
sudo chown -R $USER $HOME/.cache

# Install system libs for python packages
sudo apt update
sudo apt install -y libsndfile1

# Install python packages
pip install -r requirements.dev.txt -r requirements.test.txt 
pip install -e .[ecosystem]
pre-commit install

# pre-commit hooks cause permission weirdness
git config --global --add safe.directory /workspaces/weave

# Move extension installed black to black-latest
mv /usr/local/py-utils/bin/black /usr/local/py-utils/bin/black-latest