#!/bin/sh

export WEAVE_SERVER_DEBUG=true
export WEAVE_SERVER_ENABLE_LOGGING=true
export FLASK_APP=weave.weave_server

flask run --port 9994
