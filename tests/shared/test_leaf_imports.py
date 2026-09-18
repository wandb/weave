from weave.shared import constants, ids
from weave.trace_server import constants as server_constants
from weave.trace_server import ids as server_ids


def test_server_constants_preserve_shared_values():
    assert {
        name: value for name, value in vars(server_constants).items() if name.isupper()
    } == {name: value for name, value in vars(constants).items() if name.isupper()}


def test_server_id_generator_is_shared():
    assert server_ids.generate_id is ids.generate_id
