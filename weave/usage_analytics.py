import analytics
import socket

from . import context_state
from . import environment

analytics.write_key = "uJ8vZgKqTBVH6ZdhD4GZGZYsR7ucfJmb"


def hostname():
    return socket.gethostname()


identify_called = False


def _identify():
    global identify_called
    if not identify_called:
        host = hostname()
        analytics.identify(host, {"hostname": host})
    identify_called = True


def analytics_enabled():
    context_enabled = context_state.analytics_enabled()
    env_enabled = environment.usage_analytics_enabled()

    return context_enabled and env_enabled


def track(action: str, info=None):
    if not analytics_enabled():
        return
    try:
        _identify()
        if info is None:
            info = {}
        analytics.track(hostname(), action, info)
    except:
        pass


def use_called():
    track("called use")


def show_called(info=None):
    track("called show", info)
