import weave
from weave.trace.objectify import register_object


def make_op():
    @weave.op
    def say_hello(name: str):
        return "hello " + name

    return say_hello


@register_object
class CustomObject(weave.Object):
    my_name: str

    @weave.op
    def say_hello(self):
        return "hello " + self.my_name

    @classmethod
    def from_obj(cls, obj: weave.Object):
        return cls(my_name=obj.my_name)
