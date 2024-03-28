# Setting up Weave in development mode

## When do I need development mode?

You need to use Weave development mode if you:

- want to change how the weave engine itself works
- want to edit or add new javascript panels
- want to debug things that aren't working

You _don't_ need Weave development mode if you:

- want to use weave for data exploration
- want to create new weave ops
- want to create new weave panels that are compositions of existing panels

However, currently development mode is the best way to get access to the server logs, which are really helpful when things go wrong.

## Environment setup

You must use python3.9 or later.

This sets up a virtualenv using pyenv. Other systems that provide
python environments should work, but they are untested.

```
pyenv virtualenv 3.9.7 weave
pyenv local weave
```

Upgrade pip, otherwise you may end up using a broken version
of the pip dependency resolver and it will take forver to install.

```
pip install --upgrade pip
```

Install primary package deps

```
pip install -e .
pip install -r requirements.dev.txt
pip install -r requirements.test.txt
pip install -r requirements.ecosystem.txt
```

If you have an issue that looks like you need a rust compiler:

```
curl https://sh.rustup.rs -sSf | sh -s -- -y
export PATH="$HOME/.cargo/bin:$PATH"
```

Install frontend deps (on osx):

```
brew install n yarn jq pixman cairo pango
cd weave-js
yarn install
```

## Run in dev mode

Frontend dev server. This will auto-reload when any frontend files change, so you can just leave it running in a server.

```
cd weave-js
yarn install
yarn dev
```

Weave backend server. This does not currently auto-reload, so you need to restart it if you change stuff.

```
sh weave_server.sh
```

Now you should be able to go to localhost:3000 to see the weave home page.

Anywhere you use Weave, do:

```
import weave
weave.use_frontend_devmode()
```

This tells the weave API to load the frontend from the development server on port :3000. The dev frontend will talk to your running backend server on port :9994.

You can tell everything is working if the weave UI renders and you see your server print out some logs whenever you interact with weave.

## Environment variables

Some ops require environment variables to be set, like OPENAI_API_KEY. You need to set these for the server environment and your Jupyter notebook.


## Unit tests

Some of the unit tests try to run a wandb server container, and will produce 403s if that container is out of date. The container is only accessible to wandb developers currently.

For wandb developers, if you encounter 403s in unit tests do:

```
docker pull --platform linux/amd64 us-central1-docker.pkg.dev/wandb-production/images/local-testcontainer:master
```

You may need to "gcloud auth login" first.

And you may need to kill the running container by `docker ps` and then `docker kill`
