#!/bin/sh

DD_SERVICE="weave-python" DD_ENV="dev-danny" DD_LOGS_INJECTION=true \
	DD_TRACE_PROPAGATION_STYLE_EXTRACT=b3,datadog \
	DD_TRACE_PROPAGATION_STYLE_INJECT=b3,datadog \
	WEAVE_SERVER_ENABLE_LOGGING=true \
    WEAVE_SERVER_DEBUG=true \
	FLASK_ENV=development \
	FLASK_APP=weave.weave_server \
	ddtrace-run flask run --port 9994
