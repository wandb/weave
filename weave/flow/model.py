import typing
import weave
from .obj import Object


class Model(Object):
    @weave.op()
    async def predict(self, input: typing.Any) -> typing.Any: ...
