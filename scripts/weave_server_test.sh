#!/bin/sh

export WEAVE_CI=true
export WEAVE_DISABLE_ANALYTICS=true
export WEAVE_SERVER_DEBUG=true
export WEAVE_SERVER_ENABLE_LOGGING=true
export WEAVE_WANDB_GQL_NUM_TIMEOUT_RETRIES=1
export FLASK_APP=weave.weave_server

flask run --port 9994 "$@"
