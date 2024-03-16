import typing
import weave


@weave.type()
class Model:
    @weave.op()
    async def predict(self, input: typing.Any) -> typing.Any:
        ...
