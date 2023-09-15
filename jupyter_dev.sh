#!/bin/sh
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
    WEAVE_FRONTEND_DEVMODE=true jupyter notebook
)
