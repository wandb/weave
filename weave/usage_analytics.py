import analytics
import subprocess

from . import context_state

analytics.write_key = "uJ8vZgKqTBVH6ZdhD4GZGZYsR7ucfJmb"


def whoami():
    return subprocess.check_output("whoami").decode().strip()


identify_called = False


def _identify():
    global identify_called
    if not identify_called:
        who = whoami()
        analytics.identify(who, {"whoami": who})
    identify_called = True


def track(action: str, info=None):
    if not context_state.analytics_enabled():
        return
    _identify()
    if info is None:
        info = {}
    analytics.track(whoami(), action, info)


def use_called():
    track("called use")


def show_called(info=None):
    track("called show", info)
