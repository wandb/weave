from typing import Optional
import weave
import pydantic


def test_pydantic_saveload():
    class Object(pydantic.BaseModel):
        name: Optional[str] = "hello"
        description: Optional[str] = None

    class A(Object):
        model_name: str

    class B(A):
        pass

    a = B(name="my-a", model_name="my-model")

    a_type = weave.type_of(a)
    assert a_type.root_type_class().__name__ == "A"

    weave.init_local_client()
    weave.publish(a, name="my-a")

    a2 = weave.ref("my-a").get()
    assert a2.name == "my-a"
    assert a2.description == None
    assert a2.model_name == "my-model"
