import weave


def test_dictifiable(client):
    class NonDictifiable:
        attr: int

        def __init__(self, attr: int):
            self.attr = attr

    class Dictifiable:
        attr: int

        def __init__(self, attr: int):
            self.attr = attr

        def to_dict(self):
            return {"attr": self.attr}

    @weave.op
    def func(d: Dictifiable, nd: NonDictifiable) -> dict:
        return {
            "d": Dictifiable(d.attr),
            "nd": NonDictifiable(nd.attr),
        }

    val = 42
    d = Dictifiable(val)
    nd = NonDictifiable(val)
    res = func(d, nd)
    assert isinstance(res["d"], Dictifiable)
    assert res["d"].attr == val
    assert isinstance(res["nd"], NonDictifiable)
    assert res["nd"].attr == val

    call = func.calls()[0]

    assert call.inputs["d"] == {"attr": val}
    assert call.inputs["nd"].startswith(
        "<test_dictifiable.test_dictifiable.<locals>.NonDictifiable object at"
    )
    assert call.output["d"] == {"attr": val}
    assert call.output["nd"].startswith(
        "<test_dictifiable.test_dictifiable.<locals>.NonDictifiable object at"
    )
