import dataclasses
import pathlib

from . import slackapi
from . import slackapi_readexport


@dataclasses.dataclass
class Slack:
    slack_api: slackapi.SlackApi

    def channels(self):
        return sorted(self.channel(name) for name in self.slack_api.channel_names())

    def channel(self, name) -> "Channel":
        # TODO: pass in data_dir
        return Channel(self.slack_api, name)


@dataclasses.dataclass(order=True)
class Channel:
    slack: slackapi.SlackApi
    name: str

    @property
    def size(self) -> int:
        return self.slack.channel_export_size(self.name)

    @property
    def messages(self) -> list["Message"]:
        channel_messages = []
        for message in self.slack.channel_messages(self.name):
            if message["type"] != "message" or message.get("subtype"):
                # TODO: Don't drop these! Should be exposed as part of the API and filtered out.

                # actual messages from users don't have subtype set
                continue
            channel_messages.append(
                Message(message["ts"], self.name, message["text"], message["user"])
            )
        return channel_messages


@dataclasses.dataclass
class Message:
    ts: str
    channel: str
    text: str
    user_id: str


# TODO: make this work with artifacts
def open_slack_export(d: pathlib.Path) -> Slack:
    return Slack(slackapi_readexport.SlackReadExportApi(d))


def all_messages(channels: list[Channel]) -> list[Message]:
    ms = []
    for c in channels:
        ms += c.messages
    return ms
