#!/bin/sh
(
    source ./config/auth_modes.env
    WEAVE_FRONTEND_DEVMODE=true jupyter notebook
)
