import pytest

import weave
from weave.errors import WeaveInvalidStringError


def test_object_cant_have_invalid_name():
    class A(weave.Object):
        x: int

    with pytest.raises(WeaveInvalidStringError):
        a = A(x=1, name="in:valid/name")


def test_cant_publish_valid_object_with_invalid_name():
    lst = [1, 2, 3]

    with pytest.raises(WeaveInvalidStringError):
        weave.publish(lst, name="in:valid/name")
