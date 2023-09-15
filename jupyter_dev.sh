#!/bin/sh
(
    if [[ "${USE_ADMIN_ENV}" ]];
    then 
        echo "Using admin env"
        source .admin.env 
    fi 
    WEAVE_FRONTEND_DEVMODE=true jupyter notebook
)
