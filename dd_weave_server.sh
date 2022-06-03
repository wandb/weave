#!/bin/sh

DD_SERVICE="weave-python" DD_ENV="dev-shawn" DD_LOGS_INJECTION=true DD_PROFILING_ENABLED=true \
	FLASK_ENV=development FLASK_APP=weave.weave_server ddtrace-run flask run --port 9994
