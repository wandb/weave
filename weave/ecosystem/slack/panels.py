import typing
from . import slack

import weave


@weave.op()
def channels_render(
    channels: weave.Node[list[slack.Channel]],
) -> weave.panels.Table:
    return weave.panels.Table(
        channels,
        columns=[
            lambda channel: channel.channel_name(),
            # lambda channel: weave.panels.WeaveLink(
            #     channel.name(), to=lambda channel: channel  # TODO...
            # ),
            lambda channel: channel.size(),
        ],
    )


@weave.op()
def channel_render(
    channel_node: weave.Node[slack.Channel],
) -> weave.panels.Card:
    channel = typing.cast(slack.Channel, channel_node)  # type: ignore
    return weave.panels.Card(
        title=channel.channel_name(),
        subtitle="Slack channel",
        content=[
            weave.panels.CardTab(
                name="Messages",
                content=weave.panels.Table(
                    channel.messages(),
                    columns=[
                        lambda message: message.user_id(),
                        lambda message: message.text(),
                    ],
                ),
            ),
        ],
    )
