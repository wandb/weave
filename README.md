# Weave internal

This repository is for pre-release Weave development and internal usage trials.

**Do not share this repo, screenshots, or related information, with anyone outside of W&B unless you have explicit written approval from Shawn.**

# Current status

This is a very early release of Weave Jupyter. The example notebooks should work. Trying to do anything beyond what the notebooks do probably not work.

# Setup instructions

Create a new virtualenv, e.g. `pyenv virtualenv 3.9.7 weave_internal`

Then from the root of this repository run:

```
pyenv local weave_internal
pip install -e .
```

This will install weave and its dependencies in your weave_internal pyenv. It also tells any python instances running in this directory or a subdirectory to use the weave_internal pyenv (the "pyenv local" command does this by creating a file called .python-version that contains the string "weave_internal").

Now you can use any of the notebooks in this repository's root directory or the examples/ directory, or `import weave` anywhere else on your system when using the weave_internal pyenv.

# Example notebooks

Demo notebooks can be found in / and /examples.

Run

```
jupyter notebook
```

in the root directory, and then use the Jupyter browser to open them.

# Docs

Coming soon
