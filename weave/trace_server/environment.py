import os



def wf_trace_server_url() -> str:
    """The url of the web server exposing the trace interface endpoints"""
    return os.environ.get("WF_TRACE_SERVER_URL", "https://trace.wandb.ai")
