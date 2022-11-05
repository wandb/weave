#!/bin/sh

WEAVE_SERVER_ENABLE_LOGGING=true FLASK_DEBUG=1 FLASK_APP=weave.weave_server flask run --port 9994
