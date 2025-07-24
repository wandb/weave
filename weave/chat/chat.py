from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient

from weave.chat.completions import Completions


class Chat:
    def __init__(self, client: "WeaveClient"):
        """This class exists to mirror openai.resources.chat.chat.Chat
        so we can have a drop-in compatible client.chat.completions.create call.
        """
        self.completions = Completions(client)
