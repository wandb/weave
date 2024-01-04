#!/bin/sh
(
    source ./config/auth_modes.sh
    WEAVE_FRONTEND_DEVMODE=true jupyter notebook
)
