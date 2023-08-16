#!/bin/sh

WEAVE_SERVER_DEBUG=true WEAVE_SERVER_ENABLE_LOGGING=true FLASK_APP=weave.weave_server WEAVE_LOG_FORMAT=integration_tests flask run --port 9994
