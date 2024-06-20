import typing

import weave
from weave.legacy.ecosystem.slack import slack


@weave.type()
class SlackMessagesPanel(weave.Panel):
    id = "SlackMessagesPanel"
    input_node: weave.Node[list[slack.Message]]

    @weave.op()
    def render(self) -> weave.legacy.panels.Table:
        messages = typing.cast(list[slack.Message], self.input_node)  # type: ignore
        return weave.legacy.panels.Table(
            messages,
            columns=[
                lambda message: message.user_id,
                lambda message: message.text,
            ],
        )


@weave.type()
class SlackChannelsPanel(weave.Panel):
    id = "SlackChannelsPanel"
    input_node: weave.Node[list[slack.Channel]]

    @weave.op()
    def render(self) -> weave.legacy.panels.Table:
        return weave.legacy.panels.Table(
            self.input_node,
            columns=[
                lambda channel: channel.channel_name,
                lambda channel: channel.size(),
            ],
        )


@weave.type()
class SlackChannelPanel(weave.Panel):
    id = "SlackChannelPanel"
    input_node: weave.Node[slack.Channel]

    @weave.op()
    def render(self) -> weave.legacy.panels.Card:
        channel = typing.cast(slack.Channel, self.input_node)  # type: ignore
        return weave.legacy.panels.Card(
            title=channel.channel_name,
            subtitle="Slack channel",
            content=[
                weave.legacy.panels.CardTab(
                    name="Messages", content=SlackMessagesPanel(channel.messages())
                ),
            ],
        )


@weave.type()
class SlackPanel(weave.Panel):
    id = "SlackPanel"
    input_node: weave.Node[slack.Slack]

    @weave.op()
    def slack_render(self) -> weave.legacy.panels.Card:
        s = typing.cast(slack.Slack, self.input_node)  # type: ignore
        return weave.legacy.panels.Card(
            title="Slack export data",
            subtitle="",
            content=[
                weave.legacy.panels.CardTab(
                    name="Channels", content=SlackChannelsPanel(s.channels())
                ),
            ],
        )
