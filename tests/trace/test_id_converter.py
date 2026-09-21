import pytest

from tests.trace.id_converter import DummyIdConverter


@pytest.mark.parametrize(
    ("kind", "external"),
    [
        ("project_id", "shawn/test-project"),
        ("run_id", "test-run"),
        ("user_id", "shawn"),
    ],
)
def test_id_mapping_round_trips_without_backend_imports(kind, external):
    converter = DummyIdConverter()
    to_internal = getattr(converter, f"ext_to_int_{kind}")
    to_external = getattr(converter, f"int_to_ext_{kind}")
    internal = to_internal(external)
    assert internal != external
    assert to_internal(external) == internal
    assert to_external(internal) == external
