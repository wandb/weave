import typing
import weave


@weave.type()
class Model:
    @weave.op()
    def predict(self, input: typing.Any) -> typing.Any:
        ...
