import hashlib
import importlib
import json
from pathlib import Path

import pytest
from pydantic.errors import PydanticInvalidForJsonSchema

pytestmark = pytest.mark.trace_server


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("trace_server_interface", "CallSchema"),
        ("common_interface", "SortBy"),
        ("common_interface", "_warned_field_sets"),
        ("errors", "InvalidRequest"),
        ("validation_util", "CHValidationError"),
        ("agents.schema", "NormalizedMessage"),
        ("interface.query", "Query"),
        ("interface.builtin_object_classes.provider", "Provider"),
    ],
)
def test_legacy_contract_import_has_one_identity(module: str, name: str) -> None:
    legacy = importlib.import_module(f"weave.trace_server.{module}")
    shared = importlib.import_module(f"weave.shared.trace_server.{module}")
    assert vars(legacy)[name] is vars(shared)[name]


# Captured before extraction at 648c39783259b2981a08fadbd2daeedeffa4eef6.
SCHEMAS = json.loads(
    Path(__file__).with_name("trace_contract_schema_digests.json").read_text()
)


@pytest.mark.parametrize("module", SCHEMAS)
def test_public_schema_is_unchanged(module: str) -> None:
    legacy = importlib.import_module(module)
    shared = importlib.import_module(
        module.replace("weave.trace_server", "weave.shared.trace_server")
    )
    schemas = {}
    for name in SCHEMAS[module]["names"]:
        model = vars(shared)[name]
        assert vars(legacy)[name] is model
        try:
            schemas[name] = model.model_json_schema()
        except PydanticInvalidForJsonSchema as error:
            schemas[name] = {"schema_error": str(error)}
    digest = hashlib.sha256(json.dumps(schemas, sort_keys=True).encode()).hexdigest()
    assert digest == SCHEMAS[module]["sha256"]
