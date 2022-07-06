# Weave internal

This repository is for pre-release Weave development and internal W&B usage.

**Do not share this repo, screenshots, or related information, with anyone outside of W&B unless you have explicit written approval from Shawn.**

# Q3 2022 Goals

Our Q3 goal for Weave is to enable ML engineers at W&B to start making new W&B experiences (gated behind feature flags for now)!

# Support

Please send questions, feedback & issues in the W&B #weave Slack channel.

# Documentation

Weave documentation is currently maintained in our internal W&B notion: https://www.notion.so/wandbai/Weave-Python-b4a5ccade5ed460ba0d6ca03e7b82bf2

# Setup instructions

Create a new virtualenv, e.g. `pyenv virtualenv 3.9.7 weave_internal`

Then from the root of this repository run:

```
pyenv local weave_internal
pip install -e .
```

This will install weave and its dependencies in your weave_internal pyenv. It also tells any python instances running in this directory or a subdirectory to use the weave_internal pyenv (the "pyenv local" command does this by creating a file called .python-version that contains the string "weave_internal").

Now you can use any of the notebooks in this repository's root directory or the examples/ directory, or `import weave` anywhere else on your system when using the weave_internal pyenv.

If you are going to submit PRs to weave-internal, please also install the pre-commit hooks:

```
pip install -r requirements.dev.txt
pre-commit install
```

# Example notebooks

Demo notebooks can be found in / and /examples.

Run

```
jupyter notebook
```

in the root directory, and then use the Jupyter browser to open them.
