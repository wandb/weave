from .jack_extract import do_jack_extract
import os

def test_jack_repro():
    os.environ["WF_TRACE_SERVER_URL"] = "http://127.0.01:6345"
    do_jack_extract()
