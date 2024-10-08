#!/usr/bin/env bash

# Allows for relative paths

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )

if [[ "${USE_ADMIN_AUTH}" ]];
then 
    echo "Using admin auth"
    export $(cat $parent_path/.admin.env  | xargs)
else
    if [[ "${USE_USER_AUTH}" ]];
    then 
        echo "Using user auth"
        export $(cat $parent_path/.wb_api.env  | xargs)
    else
        echo "Using no auth"
    fi 
fi
