# Instructions

Create a new virtualenv, e.g. `pyenv virtualenv 3.9.7 weave_internal`

Then from the root of this repository run:

```
pyenv local weave_internal
pip install -e .
```

This will install weave and its dependencies in your weave_internal pyenv. It also tells any python instances running in this directory or a subdirectory to use the weave_internal pyenv (the "pyenv local" command does this by creating a file called .python-version that contains the string "weave_internal").

Now you can use any of the notebooks in this repository's root directory or the examples/ directory, or `import weave` anywhere else on your system when using the weave_internal pyenv.
