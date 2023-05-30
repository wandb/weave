#!/bin/sh

WEAVE_SERVER_DEBUG=true WEAVE_SERVER_ENABLE_LOGGING=true FLASK_APP=weave.weave_server flask run --port 9994
