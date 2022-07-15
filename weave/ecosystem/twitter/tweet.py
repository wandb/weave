import weave
import dataclasses


class TweetType(weave.types.ObjectType):
    def property_types(self):
        return {
            "_created_at": weave.types.String(),
            "_id": weave.types.Int(),
            "_text": weave.types.String(),
            "_truncated": weave.types.Boolean(),
            "_possibly_sensitive": weave.types.Boolean(),
        }


@weave.weave_class(weave_type=TweetType)
@dataclasses.dataclass
class Tweet:
    _id: int
    _created_at: str
    _text: str
    _truncated: bool
    _possibly_sensitive: bool

    @weave.op()
    def id(self) -> int:
        return self._id

    @weave.op()
    def created_at(self) -> str:
        return self._created_at

    @weave.op()
    def text(self) -> str:
        return self._text

    @weave.op()
    def truncated(self) -> bool:
        return self._truncated

    @weave.op()
    def possibly_sensitive(self) -> bool:
        return self._possibly_sensitive


TweetType.instance_classes = Tweet
