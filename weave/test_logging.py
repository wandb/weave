import os
import re
import requests
from . import api
from . import ops
from . import context
from . import server
from . import weave_server

import pytest


def test_logfile_created(fresh_server_logfile):

    with context.local_http_client():
        # run this to kick off a server
        assert api.use(ops.Number.__add__(3, 9)) == 12

        # check that the log file was created
        assert os.path.exists(weave_server.default_log_filename)

        with open(weave_server.default_log_filename, "r") as f:
            content = f.read()

        # check that it has a record of executing one call
        assert "execute" in content and "200" in content


def test_logfile_captures_error(fresh_server_logfile):
    # run this to kick off a server

    with context.local_http_client():
        with pytest.raises(requests.exceptions.HTTPError):
            api.use(ops.Number.__add__(3, "a"))

        # check that the log file was created
        assert os.path.exists(weave_server.default_log_filename)

        with open(weave_server.default_log_filename, "r") as f:
            content = f.read()

        # check that it has a record of executing one call
        assert "execute" in content and "500" in content


def test_log_2_app_instances_different_threads(fresh_server_logfile):
    # kick off two http servers

    with context.local_http_client():
        with context.local_http_client():
            with pytest.raises(requests.exceptions.HTTPError):
                # this one is run by server 2
                api.use(ops.Number.__add__(3, "a"))

        # this one is run by server 1
        assert api.use(ops.Number.__add__(3, 9)) == 12

    # check that the log file was created
    assert os.path.exists(weave_server.default_log_filename)

    with open(weave_server.default_log_filename, "r") as f:
        content = f.read()

    # check that it has a record of executing one call
    assert "execute" in content
    assert "200" in content

    # and we have an error
    assert "500" in content

    # check that there are two threads logged
    print("LOG CONTENT", content)
    threads = set(re.findall(r"\(Thread (.+?)\)", content))
    assert len(threads) == 2


def test_capture_server_logs_captures_server_logs(fresh_server_logfile, capsys):
    server.capture_weave_server_logs()

    with context.local_http_client():
        # run this to kick off a server
        assert api.use(ops.Number.__add__(3, 9)) == 12

        # check that the log file was created
        assert os.path.exists(weave_server.default_log_filename)

        with open(weave_server.default_log_filename, "r") as f:
            content = f.read()

        # check that it has a record of executing one call
        assert "execute" in content and "200" in content

        # check that the same stuff appears in the captured stream logs
        capresult = capsys.readouterr()
        stderr = capresult.err
        assert "execute" in stderr and "200" in stderr
