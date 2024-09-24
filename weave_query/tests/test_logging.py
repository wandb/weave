import os
import re

import pytest
import requests

from weave import weave_server
from weave.legacy.weave import api, context, logs, ops, server


def test_logfile_created(fresh_server_logfile):
    server.capture_weave_server_logs()
    with context.local_http_client():
        # run this to kick off a server
        assert api.use(ops.Number.__add__(3, 9)) == 12

        # check that the log file was created
        log_filename = logs.default_log_filename()
        assert log_filename
        assert os.path.exists(log_filename)

        with open(log_filename, "r") as f:
            content = f.read()

        # check that it has a record of executing one call
        assert "execute" in content and "200" in content


def test_logfile_captures_error(fresh_server_logfile):
    # run this to kick off a server
    server.capture_weave_server_logs()

    with context.local_http_client():
        with pytest.raises(requests.exceptions.HTTPError):
            api.use(ops.Number.__add__(4, "a"))

        # check that the log file was created
        log_filename = logs.default_log_filename()
        assert log_filename
        assert os.path.exists(log_filename)

        with open(log_filename, "r") as f:
            content = f.read()

        # check that it has a record of executing one call
        assert "execute" in content and "500" in content


def test_log_2_app_instances_different_threads(fresh_server_logfile):
    # kick off two http servers
    server.capture_weave_server_logs()
    with context.local_http_client():
        with context.local_http_client():
            with pytest.raises(requests.exceptions.HTTPError):
                # this one is run by server 2
                api.use(ops.Number.__add__(3, "a"))

        # this one is run by server 1
        assert api.use(ops.Number.__add__(3, 9)) == 12

    # check that the log file was created
    log_filename = logs.default_log_filename()
    assert log_filename
    assert os.path.exists(log_filename)

    with open(log_filename, "r") as f:
        content = f.read()

    # check that it has a record of executing one call
    assert "execute" in content
    assert "200" in content

    # and we have an error
    assert "500" in content

    # check that there are two threads logged
    threads = set(re.findall(r"Weave Port: (.+?)\)", content))
    assert len(threads) == 2


def test_capture_server_logs_captures_server_logs(fresh_server_logfile, capsys):
    server.capture_weave_server_logs()

    with context.local_http_client():
        # run this to kick off a server
        assert api.use(ops.Number.__add__(3, 9)) == 12

        # check that the log file was created
        log_filename = logs.default_log_filename()
        assert log_filename
        assert os.path.exists(log_filename)

        with open(log_filename, "r") as f:
            content = f.read()

        # check that it has a record of executing one call
        assert "execute" in content and "200" in content

        # check that the same stuff appears in the captured stream logs
        capresult = capsys.readouterr()
        stderr = capresult.err
        assert "execute" in stderr and "200" in stderr
