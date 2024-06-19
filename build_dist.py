#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess

if os.path.exists("dist"):
    shutil.rmtree("dist")

# Check that MANIFEST.in is up to date.  We ignore the following directories, if any new
# directories are added they must be added as "graft weave/<dir>" to MANIFEST.in
ignored_dirs = set(
    [
        "__pycache__",
        ".hypothesis",
        ".pytest_cache",
        "docs",
        "test_scripts",
        "testdata",
        "tests",
    ]
)
known_dirs = set()
with open("MANIFEST.in") as f:
    for line in f.readlines():
        if line.startswith("graft"):
            known_dirs.add(line.split(" ")[1].strip().replace("weave/", ""))

bad_dirs = set()
for name in os.listdir("./weave"):
    if os.path.isfile(os.path.join("./weave", name)):
        continue
    if name in ignored_dirs:
        continue
    if name not in known_dirs:
        bad_dirs.add(name)

if len(bad_dirs) > 0:
    raise ValueError(
        f"Unknown directories: {bad_dirs}, modify MANIFEST.in or build.py to include them."
    )

if os.getenv("WEAVE_SKIP_BUILD") == None:
    subprocess.run(["bash", "weave/frontend/build.sh"], check=True)
else:
    print("!!! Skipping frontend build !!!")

subprocess.run(["python", "-m", "build"], check=True)

print("Push to pypi with: python -m twine upload --repository pypi dist/*")
print(
    "  replace pypi with pypitest for testing, install with --index-url https://test.pypi.org/simple/"
)
