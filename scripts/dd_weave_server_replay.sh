#!/bin/sh

WEAVE_SERVER_DEBUG=true \
DD_SERVICE="weave-python" DD_ENV="dev-$(whoami)" DD_LOGS_INJECTION=true \
	WEAVE_SERVER_ENABLE_LOGGING=true FLASK_APP=weave.weave_server ddtrace-run flask run --port 9994
