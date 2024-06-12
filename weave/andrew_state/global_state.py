# forget contexts, let's just use globals for now and then revisit
import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..andrew_client import Client

client: Optional["Client"] = None
client_lock = threading.Lock()
# There is also a run context?  idk what this is


def get_client() -> "Client":
    return client


def set_client(c: "Client") -> None:
    global client
    if c is not None and client is None:
        with client_lock:
            if client is None:
                client = c

    elif c is None and client is not None:
        with client_lock:
            if client is not None:
                client = None
