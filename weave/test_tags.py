from . import tags


class A:
    def __init__(self, a):
        self.a = a


class Num(int):
    pass


def test_tags_obj():
    a = A(5)
    x = tags.with_tag(a, "a", 19)
    assert tags.get_tag(x, "a") == 19
    assert tags.get_tags(x) == {"a": 19}


def test_tags_inherit_from_primitive():
    a = Num(5)
    x = tags.with_tag(a, "a", 19)
    assert tags.get_tag(x, "a") == 19


def test_tags_primitive():
    a = 5
    assert tags.get_tags(a) == None
    assert tags.get_tag(a, "a") == None
    x = tags.with_tag(a, "a", 19)
    assert tags.get_tag(x, "a") == 19
    b = 5
    assert tags.get_tag(b, "a") == None
