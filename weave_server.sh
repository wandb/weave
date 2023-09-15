#!/bin/sh

# We could set WEAVE_BACKEND_HOST=http://localhost:9994/__weave but the frontend dev server
# automatically forwards so it shouldn't be necessary.
(
    if [[ "${USE_ADMIN_AUTH}" ]];
    then 
        echo "Using admin auth"
        source .admin.env 
    else
        if [[ "${USE_USER_AUTH}" ]];
        then 
            echo "Using user auth"
            source .wb_api.env 
        else
            echo "Using no auth"
        fi 
    fi 
    WEAVE_DISABLE_ANALYTICS=true WEAVE_SERVER_ENABLE_LOGGING=true FLASK_DEBUG=1 FLASK_APP=weave.weave_server flask run --port 9994
)
