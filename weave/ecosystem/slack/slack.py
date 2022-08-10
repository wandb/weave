import weave

from . import slackapi_readexport


@weave.type()
class Message:
    ts: str
    channel: str
    _text: str
    _user_id: str

    @weave.op()
    def user_id(self) -> str:
        return self._user_id

    @weave.op()
    def text(self) -> str:
        return self._text


@weave.type()
class Channel:
    # TODO: this should be SlackApi, but serialization doesn't work when we use a Protocol here :(
    slack_api: slackapi_readexport.SlackReadExportApi
    _name: str

    @weave.op()
    # Damn VarNode conflict
    def channel_name(self) -> str:
        return self._name

    @weave.op()
    def size(self) -> int:
        return self.slack_api.channel_export_size(self._name)

    @weave.op()
    def messages(self) -> list[Message]:
        channel_messages = []
        for message in self.slack_api.channel_messages(self._name):
            if message["type"] != "message" or message.get("subtype"):
                # TODO: Don't drop these! Should be exposed as part of the API and filtered out.

                # actual messages from users don't have subtype set
                continue
            channel_messages.append(
                Message(message["ts"], self._name, message["text"], message["user"])
            )
        return channel_messages


@weave.type()
class Slack:
    # TODO: this should be SlackApi, but serialization doesn't work when we use a Protocol here :(
    slack_api: slackapi_readexport.SlackReadExportApi

    @weave.op()
    def channels(self) -> list[Channel]:
        # TODO: sorted?
        return [
            self.channel.resolve_fn(self, name)
            for name in self.slack_api.channel_names()
        ]

    @weave.op()
    def channel(self, name: str) -> Channel:
        # TODO: pass in data_dir
        return Channel(self.slack_api, name)


# TODO: make this work with artifacts
@weave.op(render_info={"type": "function"})
def open_slack_export(d: str) -> Slack:
    return Slack(slackapi_readexport.SlackReadExportApi(weave.ops.VersionedDir(d)))


def all_messages(channels: list[Channel]) -> list[Message]:
    ms = []
    for c in channels:
        ms += c.messages
    return ms
