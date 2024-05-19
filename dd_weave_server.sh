#!/bin/sh

DD_SERVICE="weave-python" DD_ENV="dev-$(whoami)" DD_LOGS_INJECTION=true \
	DD_TRACE_PROPAGATION_STYLE_EXTRACT=b3,datadog \
	DD_TRACE_PROPAGATION_STYLE_INJECT=b3,datadog \
	WEAVE_DISABLE_ANALYTICS=true \	
	WEAVE_SERVER_ENABLE_LOGGING=true \
	FLASK_ENV=development \
	FLASK_APP=weave.weave_server \
	ddtrace-run flask run --port 9994

# This runs with the datadog profiler on, but it is expensive!
# I noticed a 2x increase in query time for some queries
# DD_SERVICE="weave-python" DD_ENV="dev-$(whoami)" DD_LOGS_INJECTION=true DD_PROFILING_ENABLED=true \
# 	WEAVE_SERVER_ENABLE_LOGGING=true FLASK_ENV=development FLASK_APP=weave.weave_server ddtrace-run flask run --port 9994
