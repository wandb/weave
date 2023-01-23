import weave

from . import slackapi_readexport


@weave.type()
class Message:
    ts: str
    channel: str
    text: str
    user_id: str


@weave.type()
class Channel:
    # TODO: this should be SlackApi, but serialization doesn't work when we use a Protocol here :(
    slack_api: slackapi_readexport.SlackReadExportApi
    channel_name: str  # can't use 'name' because of VarNode attr conflict :(

    @weave.op()
    def size(self) -> int:
        return self.slack_api.channel_export_size(self.channel_name)

    @weave.op()
    def messages(self) -> list[Message]:
        channel_messages = []
        for message in self.slack_api.channel_messages(self.channel_name):
            if message["type"] != "message" or message.get("subtype"):
                # TODO: Don't drop these! Should be exposed as part of the API and filtered out.

                # actual messages from users don't have subtype set
                continue
            channel_messages.append(
                Message(
                    message["ts"], self.channel_name, message["text"], message["user"]
                )
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


# Marked as impure, because we need to read the directory d on every execution.
# TODO: This should not need to be manually marked. We know that VersionedDir reads
#     a local dir. One way to fix this would be to use Weave ops for constructors
#     instead of Python class constructors (ie we'd have a versioned_dir op that is
#     impure, and everything downstream of it would be impure until we hit an existing
#     artifact version).
@weave.op(render_info={"type": "function"}, pure=False)
def open_slack_export(d: str) -> Slack:
    # Note from Shawn: I changed this because I got rid of "VersionedDir". Now passing
    # Dir which is more like DirInfo. Don't know if this still works.
    return Slack(slackapi_readexport.SlackReadExportApi(weave.Dir(d, 0, {}, {})))


def all_messages(channels: list[Channel]) -> list[Message]:
    ms = []
    for c in channels:
        ms += c.messages
    return ms
