#!/bin/sh

WEAVE_SERVER_ENABLE_LOGGING=true FLASK_ENV=development FLASK_APP=weave.weave_server flask run --port 9994
