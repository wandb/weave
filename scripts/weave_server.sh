#!/bin/sh

# We could set WEAVE_BACKEND_HOST=http://localhost:9994/__weave but the frontend dev server
# automatically forwards so it shouldn't be necessary.
(
    source ./config/auth_modes.sh
    WEAVE_DISABLE_ANALYTICS=true WEAVE_SERVER_ENABLE_LOGGING=true FLASK_DEBUG=1 FLASK_APP=weave.weave_server flask run --port 9994
)
