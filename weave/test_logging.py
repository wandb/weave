import os
import re
import json
from . import api
from . import ops
from . import context

import pytest


def test_logfile_created(isolated_filesystem):

    with context.local_http_client():
        # run this to kick off a server
        assert api.use(ops.Number.__add__(3, 9)) == 12

        # check that the log file was created
        log_filename = f"./.weave/log/{os.getpid()}.log"
        assert os.path.exists(log_filename)

        with open(log_filename, "r") as f:
            content = f.read()

        # check that it has a record of executing one call
        assert "execute" in content and "200" in content


def test_logfile_captures_error(isolated_filesystem):
    # run this to kick off a server

    with context.local_http_client():
        with pytest.raises(json.JSONDecodeError):
            api.use(ops.Number.__add__(3, "a"))

        # check that the log file was created
        log_filename = f"./.weave/log/{os.getpid()}.log"
        assert os.path.exists(log_filename)

        with open(log_filename, "r") as f:
            content = f.read()

        # check that it has a record of executing one call
        assert "execute" in content and "500" in content


def test_log_2_app_instances_different_threads(isolated_filesystem):
    # kick off two http servers

    with context.local_http_client():
        with context.local_http_client():
            with pytest.raises(json.JSONDecodeError):
                # this one is run by server 2
                api.use(ops.Number.__add__(3, "a"))

        # this one is run by server 1
        assert api.use(ops.Number.__add__(3, 9)) == 12

    # check that the log file was created
    log_filename = f"./.weave/log/{os.getpid()}.log"
    assert os.path.exists(log_filename)

    with open(log_filename, "r") as f:
        content = f.read()

    # check that it has a record of executing one call
    assert "execute" in content and "500" in content and "200" in content
    threads = re.findall(r"\(Thread (.+)\)", content)

    assert len(threads) == 2
    assert threads[0][0] != threads[1][0]
