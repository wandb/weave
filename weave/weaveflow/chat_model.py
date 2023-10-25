import typing
import weave


@weave.type()
class ChatModel:
    @weave.op()
    def complete(self, messages: typing.Any) -> typing.Any:
        ...
