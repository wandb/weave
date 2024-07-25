from pydantic import Field

import weave


def test_object_mutation_saving(client):
    class Thing(weave.Object):
        a: str
        b: int
        c: float

    thing = Thing(a="hello", b=1, c=4.2)
    ref = weave.publish(thing)

    thing2 = ref.get()
    assert thing2.a == "hello"
    assert thing2.b == 1
    assert thing2.c == 4.2

    thing2.a = "new"  # TODO: Should we ignore this?
    thing2.a = "newer"
    thing2.b = 2

    assert len(thing2.mutations) == 3

    ref2 = weave.publish(thing2)
    thing3 = ref2.get()
    assert thing3.a == "newer"
    assert thing3.b == 2
    assert thing3.c == 4.2


def test_list_mutation_saving(client):
    lst = [1, 2, 3]
    ref = weave.publish(lst)

    lst2 = ref.get()
    assert lst2 == [1, 2, 3]

    lst2[0] = 100
    lst2.append(4)
    lst2.extend([5])
    lst2 += [6]
    print(f"{lst2=}")
    ref2 = weave.publish(lst2)
    print(f"{ref2=}")

    lst3 = ref2.get()
    print(f"{lst3=}")
    assert lst3 == [100, 2, 3, 4, 5, 6]

    # lst2.append(4)
    # ref2 = weave.publish(lst2)
    # lst3 = ref2.get()


def test_dict_mutation_saving(client):
    # TODO: Today we assume all the keys must be str?
    d = {"a": 1, "b": 2}
    ref = weave.publish(d)

    d2 = ref.get()
    assert d2 == {"a": 1, "b": 2}

    d2["new_key"] = 3
    d2["b"] = "new_value"
    ref2 = weave.publish(d2)

    d3 = ref2.get()
    assert d3 == {"a": 1, "b": "new_value", "new_key": 3}


def test_object_mutation_saving_nested(client):
    class A(weave.Object):
        b: int = 1

    class C(weave.Object):
        a: A = Field(default_factory=A)

    class D(weave.Object):
        a: A = Field(default_factory=A)
        c: C = Field(default_factory=C)

    d = D()
    ref = weave.publish(d)

    d2 = ref.get()
    assert d2.a.b == 1
    assert d2.c.a.b == 1

    d2.a = A(b=2)
    d2.c = C(a=A(b=3))
    ref2 = weave.publish(d2)

    d3 = ref2.get()
    assert d3.a.b == 2
    assert d3.c.a.b == 3


def test_list_mutation_saving_nested(client):
    lst = [1, 2, 3]
    ref = weave.publish(lst)

    lst2 = [4, 5, 6]
    ref2 = weave.publish(lst2)

    lst3 = ref.get()
    assert lst3 == [1, 2, 3]

    lst4 = ref2.get()
    assert lst4 == [4, 5, 6]

    lst3.append(lst4)
    ref5 = weave.publish(lst3)

    lst5 = ref5.get()
    assert lst5 == [1, 2, 3, [4, 5, 6]]


def test_dict_mutation_saving_nested(client):
    d = {"a": 1, "b": 2}
    ref = weave.publish(d)

    d2 = {"c": 3, "d": 4}
    ref2 = weave.publish(d2)

    d3 = ref.get()
    assert d3 == {"a": 1, "b": 2}

    d4 = ref2.get()
    assert d4 == {"c": 3, "d": 4}

    d3["e"] = d4
    ref5 = weave.publish(d3)

    d5 = ref5.get()
    assert d5 == {
        "a": 1,
        "b": 2,
        "e": {"c": 3, "d": 4},
    }


def test_mutation_saving_nested(client):
    class A(weave.Object):
        b: int

    class B(weave.Object):
        a: A
        c: list[int]
        d: list[list[str]]
        e: dict[str, int]
        f: dict[str, dict[str, str]]

    class G(weave.Object):
        a: A
        b: B

    g = G(
        a=A(b=1),
        b=B(
            a=A(b=2),
            c=[3, 4],
            d=[["x", "y"], ["z"]],
            e={"a": 5, "b": 6},
            f={"c": {"d": "e"}},
        ),
    )
    ref = weave.publish(g)

    g2 = ref.get()
    assert g2.a.b == 1
    assert g2.b.a.b == 2
    assert g2.b.c == [3, 4]
    assert g2.b.d == [["x", "y"], ["z"]]
    assert g2.b.e == {"a": 5, "b": 6}
    assert g2.b.f == {"c": {"d": "e"}}

    g2.b.c = [7, 8]
    g2.b.d = [["p", "q"], ["r", "s"]]
    g2.b.e = {"c": 9}
    g2.b.f = {"d": {"e": "f"}}
    print(f"{g2=}")
    print(f"{g2.b=}")
    ref2 = weave.publish(g2)

    g3 = ref2.get()
    print(f"{g3=}")
    assert g3.a.b == 1
    assert g3.b.a.b == 2
    print(f"{g3.b=}")
    assert g3.b.c == [7, 8]
    assert g3.b.d == [["p", "q"], ["r", "s"]]
    assert g3.b.e == {"c": 9}
    assert g3.b.f == {"d": {"e": "f"}}


def test_object_mutation2(client):
    class A(weave.Object):
        b: int

    class B(weave.Object):
        a: A

    class C(weave.Object):
        b: B

    c = C(b=B(a=A(b=1)))
    ref = weave.publish(c)

    c2 = ref.get()
    print(f"{c2=}")
    # c2.b.a.b = 2
    thing = B(a=A(b=2))
    print(f"{thing.a=}")
    c2.b = thing
    print(f"{c2.b.a=}")
    # c2.b.a = A(b=2)
    # print(f">>> {c2.b.a.b=}")

    print(f"{c2=}")
    print(f"{c2._is_dirty=}")
    # print(f"{c2.b._is_dirty=}")
    # print(f"{c2.b.a._is_dirty=}")
    print(f"{c2.b.a.b=}")

    ref2 = weave.publish(c2)

    c3 = ref2.get()
    print(f"{c3=}")
    print(f"{c3.b=}")
    print(f"{c3.b.a=}")
    print(f"{c3.b.a.b=}")
    assert c3.b.a.b == 2
