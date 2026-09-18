from weave.shared.ids import generate_id
from weave.trace_server.ids import generate_id as generate_id_legacy


def test_generate_id_is_uuidv7_shaped() -> None:
    value = generate_id()
    parts = value.split("-")
    assert len(parts) == 5
    assert tuple(len(p) for p in parts) == (8, 4, 4, 4, 12)
    assert parts[2][0] == "7"


def test_generate_id_values_differ() -> None:
    assert generate_id() != generate_id()


def test_trace_server_ids_reexports_the_same_function() -> None:
    assert generate_id is generate_id_legacy
