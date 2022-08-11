# The idea is that we provide the same interface from reading the Slack Api, or a Slack data export
import typing


class SlackApi(typing.Protocol):
    def channel_names(self):
        ...

    def channel_export_size(self, channel_name: str):
        ...

    # Returns a dict in the slack export format. TODO
    def channel_messages(self, channel_name: str):
        ...
