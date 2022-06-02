# Weave internal

This repository is for pre-release Weave development and internal usage trials.

**Do not share this repo, screenshots, or related information, with anyone outside of W&B unless you have explicit written approval from Shawn.**

# Current status

This is a very early release of Weave Jupyter. The example notebooks should work. Trying to do anything beyond what the notebooks do probably will not work.

The code contained herein is of mixed quality. We are starting a cleanup pass now.

# Getting involved

We'd love for you to start playing with Weave Python! Unfortunately there are currently no docs, or even reasonable explanations of what this is. Sorry about that! Try the setup instructions here, and then run the notebooks.

Please send any and all feedback to Shawn and Danny in the W&B #weave Slack channel. We are happy to take questions, troubleshoot issues, etc.

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

# Development

Install pre commit hooks

```
pip install -r requirements.dev.txt
pre-commit install
```

### Enable frontend devmode

- Run a frontend dev server on 3000:

In the W&B core repo (for now, later we'll move this out to a new repo):

```
git checkout weave-python/master
cd frontends/app/weave-ui && yarn dev
```

- Enable frontend dev mode in python

```
weave.enable_frontend_devmode()
```

### Build the bundle for production

Go to the weave ui directory and build the bundle

```
cd core/frontends/app/weave-ui && yarn build
```

Copy it over to weave-python

```
rm -rf $WEAVE_ROOT/weave-internal/weave/frontend && cp -r build/ $WEAVE_ROOT/weave-internal/weave/frontend
```
