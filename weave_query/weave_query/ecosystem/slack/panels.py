import typing

import weave_query as weave
import weave_query
from weave_query.ecosystem.slack import slack


@weave.type()
class SlackMessagesPanel(weave.Panel):
    id = "SlackMessagesPanel"
    input_node: weave.Node[list[slack.Message]]

    @weave.op()
    def render(self) -> weave_query.panels.Table:
        messages = typing.cast(list[slack.Message], self.input_node)  # type: ignore
        return weave_query.panels.Table(
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
    def render(self) -> weave_query.panels.Table:
        return weave_query.panels.Table(
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
    def render(self) -> weave_query.panels.Card:
        channel = typing.cast(slack.Channel, self.input_node)  # type: ignore
        return weave_query.panels.Card(
            title=channel.channel_name,
            subtitle="Slack channel",
            content=[
                weave_query.panels.CardTab(
                    name="Messages", content=SlackMessagesPanel(channel.messages())
                ),
            ],
        )


@weave.type()
class SlackPanel(weave.Panel):
    id = "SlackPanel"
    input_node: weave.Node[slack.Slack]

    @weave.op()
    def slack_render(self) -> weave_query.panels.Card:
        s = typing.cast(slack.Slack, self.input_node)  # type: ignore
        return weave_query.panels.Card(
            title="Slack export data",
            subtitle="",
            content=[
                weave_query.panels.CardTab(
                    name="Channels", content=SlackChannelsPanel(s.channels())
                ),
            ],
        )
