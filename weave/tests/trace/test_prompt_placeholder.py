from weave.flow.prompt.placeholder import Placeholder


def test_placeholder_initialization():
    p1 = Placeholder("name")
    assert p1.name == "name"
    assert p1.type == "string"
    assert p1.default is None

    p2 = Placeholder("age", type="integer", default="30")
    assert p2.name == "age"
    assert p2.type == "integer"
    assert p2.default == "30"


def test_placeholder_as_str():
    p1 = Placeholder("name")
    assert str(p1) == "{name}"

    p2 = Placeholder("age", type="integer", default="30")
    assert str(p2) == "{age type:integer default:30}"


def test_placeholder_to_json():
    p1 = Placeholder("name")
    assert p1.to_json() == {"name": "name", "type": "string"}

    p2 = Placeholder("age", type="integer", default="30")
    assert p2.to_json() == {"name": "age", "type": "integer", "default": "30"}


def test_placeholder_repr():
    p1 = Placeholder("name")
    assert repr(p1) == "Placeholder(name='name', type='string')"

    p2 = Placeholder("age", type="integer", default="30")
    assert repr(p2) == "Placeholder(name='age', type='integer', default='30')"


def test_placeholder_from_str():
    p1 = Placeholder.from_str("name")
    assert p1.name == "name"
    assert p1.type == "string"
    assert p1.default is None

    p2 = Placeholder.from_str("age type:integer default:30")
    assert p2.name == "age"
    assert p2.type == "integer"
    assert p2.default == "30"


def test_placeholder_equality():
    p1 = Placeholder(name="test", type="string", default="default")
    p2 = Placeholder(name="test", type="string", default="default")
    p3 = Placeholder(name="test", type="string", default="different")
    p4 = Placeholder(name="different", type="string", default="default")

    assert p1 == p2
    assert p1 != p3
    assert p1 != p4
    assert p1 != "not a placeholder"

    # Test that placeholders can be used as dictionary keys
    d = {p1: "value"}
    assert d[p2] == "value"
    assert p3 not in d
    assert p4 not in d
