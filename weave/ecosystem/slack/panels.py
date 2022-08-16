import typing
from . import slack

import weave


@weave.op()
def messages_render(
    messages_node: weave.Node[list[slack.Message]],
) -> weave.panels.Table:
    messages = typing.cast(list[slack.Message], messages_node)  # type: ignore
    return weave.panels.Table(
        messages,
        columns=[
            lambda message: message.user_id,
            lambda message: message.text,
        ],
    )


@weave.op()
def channels_render(
    channels: weave.Node[list[slack.Channel]],
) -> weave.panels.Table:
    return weave.panels.Table(
        channels,
        columns=[
            lambda channel: channel.channel_name,
            lambda channel: channel.size(),
        ],
    )


@weave.op()
def channel_render(
    channel_node: weave.Node[slack.Channel],
) -> weave.panels.Card:
    channel = typing.cast(slack.Channel, channel_node)  # type: ignore
    return weave.panels.Card(
        title=channel.channel_name,
        subtitle="Slack channel",
        content=[
            weave.panels.CardTab(
                name="Messages", content=messages_render(channel.messages())
            ),
        ],
    )


@weave.op()
def slack_render(
    slack_node: weave.Node[slack.Slack],
) -> weave.panels.Card:
    s = typing.cast(slack.Slack, slack_node)  # type: ignore
    return weave.panels.Card(
        title="Slack export data",
        subtitle="",
        content=[
            weave.panels.CardTab(
                name="Channels", content=channels_render(s.channels())
            ),
        ],
    )
