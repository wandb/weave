# forget contexts, let's just use globals for now and then revisit
import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..andrew_client import Client

global_client: Optional["Client"] = None
global_client_lock = threading.Lock()
# There is also a run context?  idk what this is


def get_global_client() -> "Client":
    return global_client


def set_global_client(client: "Client") -> None:
    global global_client
    if client is not None and global_client is None:
        with global_client_lock:
            if global_client is None:
                global_client = client

    elif client is None and global_client is not None:
        with global_client_lock:
            if global_client is not None:
                global_client = None
