import pytest
from pydantic import ValidationError

from tests.trace_server.conftest import TEST_ENTITY
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import (
    InvalidRequest,
    NotFoundError,
    ObjectDeletedError,
    handle_server_exception,
)
from weave.trace_server.interface.builtin_object_classes.provider import (
    Provider,
    ProviderModel,
)
from weave.trace_server.llm_completion import get_custom_provider_info
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context

PROJECT_ID = f"{TEST_ENTITY}/custom-runtime-api"


def apply_runtime(
    server: tsi.FullTraceServerInterface,
    *,
    base_url: str = "https://agent.example.com/v1",
    api_key_secret: str | None = "AGENT_API_KEY",
    headers: dict[str, str] | None = None,
    runtime_ids: list[tsi.CustomRuntimeID] | None = None,
) -> tsi.CustomRuntimeApplyRes:
    return server.custom_runtime_apply(
        tsi.CustomRuntimeApplyReq(
            project_id=PROJECT_ID,
            runtime_name="support-agent",
            base_url=base_url,
            api_key_secret=api_key_secret,
            headers=headers or {},
            runtime_ids=runtime_ids
            if runtime_ids is not None
            else [tsi.CustomRuntimeID(id="support-v12", max_tokens=8192)],
        )
    )


def test_custom_runtime_apply_creates_existing_provider_objects(trace_server) -> None:
    result = apply_runtime(
        trace_server,
        headers={"X-Tenant-ID": "customer-1"},
    )

    assert result.name == "support-agent"
    assert result.base_url == "https://agent.example.com/v1"
    assert result.api_key_secret == "AGENT_API_KEY"
    assert result.headers == {"X-Tenant-ID": "customer-1"}
    assert result.runtime_ids == [
        tsi.CustomRuntimeIDRes(
            id="support-v12",
            max_tokens=8192,
            playground_id="custom::support-agent::support-v12",
        )
    ]

    provider = trace_server.obj_read(
        tsi.ObjReadReq(
            project_id=PROJECT_ID,
            object_id="support-agent",
            digest="latest",
        )
    ).obj
    assert provider.base_object_class == "Provider"
    assert provider.val["api_key_name"] == "AGENT_API_KEY"
    assert provider.val["base_url"] == "https://agent.example.com/v1"
    assert provider.val["extra_headers"] == {"X-Tenant-ID": "customer-1"}
    assert provider.val["return_type"] == "openai"
    assert provider.val["name"] == "support-agent"

    provider_model = trace_server.obj_read(
        tsi.ObjReadReq(
            project_id=PROJECT_ID,
            object_id="support-agent-support-v12",
            digest="latest",
        )
    ).obj
    assert provider_model.base_object_class == "ProviderModel"
    assert provider_model.val["name"] == "support-v12"
    assert provider_model.val["max_tokens"] == 8192
    assert provider_model.val["provider"] == provider.digest


def test_custom_runtime_apply_updates_objects_created_by_existing_ui(
    trace_server,
) -> None:
    provider = Provider(
        name="support-agent",
        base_url="https://agent.example.com/v1",
        api_key_name="AGENT_API_KEY",
    )
    provider_result = trace_server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=PROJECT_ID,
                object_id="support-agent",
                val=provider.model_dump(),
                builtin_object_class="Provider",
            )
        )
    )
    provider_model = ProviderModel(
        name="support-v12",
        provider=provider_result.digest,
        max_tokens=2048,
    )
    trace_server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=PROJECT_ID,
                object_id="support-agent-support-v12",
                val=provider_model.model_dump(),
                builtin_object_class="ProviderModel",
            )
        )
    )

    result = apply_runtime(
        trace_server,
        base_url="https://agent.example.com/v2",
        runtime_ids=[tsi.CustomRuntimeID(id="support-v12", max_tokens=8192)],
    )

    assert result.runtime_ids[0].playground_id == "custom::support-agent::support-v12"
    updated_provider = trace_server.obj_read(
        tsi.ObjReadReq(
            project_id=PROJECT_ID,
            object_id="support-agent",
            digest="latest",
        )
    ).obj
    updated_model = trace_server.obj_read(
        tsi.ObjReadReq(
            project_id=PROJECT_ID,
            object_id="support-agent-support-v12",
            digest="latest",
        )
    ).obj
    assert updated_provider.val["base_url"] == "https://agent.example.com/v2"
    assert updated_model.val["provider"] == updated_provider.digest
    assert updated_model.val["max_tokens"] == 8192


def test_custom_runtime_apply_translates_user_id_before_object_writes(
    trace_server,
) -> None:
    trace_server.custom_runtime_apply(
        tsi.CustomRuntimeApplyReq(
            project_id=PROJECT_ID,
            runtime_name="support-agent",
            base_url="https://agent.example.com/v1",
            runtime_ids=[],
            wb_user_id="external-user-id",
        )
    )
    internal_project_id = trace_server._idc.ext_to_int_project_id(PROJECT_ID)
    provider = trace_server._internal_trace_server.obj_read(
        tsi.ObjReadReq(
            project_id=internal_project_id,
            object_id="support-agent",
            digest="latest",
        )
    ).obj

    assert provider.wb_user_id == b64("external-user-id")


def test_custom_runtime_apply_replaces_runtime_ids_and_allows_optional_auth(
    trace_server,
) -> None:
    apply_runtime(
        trace_server,
        runtime_ids=[
            tsi.CustomRuntimeID(id="old", max_tokens=1024),
            tsi.CustomRuntimeID(id="kept", max_tokens=2048),
        ],
    )

    result = apply_runtime(
        trace_server,
        base_url="https://agent.example.com/v2",
        api_key_secret=None,
        headers={"Authorization": "Basic configured-in-header"},
        runtime_ids=[
            tsi.CustomRuntimeID(id="kept", max_tokens=4096),
            tsi.CustomRuntimeID(id="new"),
        ],
    )

    assert result.api_key_secret is None
    assert result.runtime_ids[1].max_tokens == 4096
    provider = trace_server.obj_read(
        tsi.ObjReadReq(
            project_id=PROJECT_ID, object_id="support-agent", digest="latest"
        )
    ).obj
    assert provider.val["api_key_name"] == ""
    assert provider.val["extra_headers"] == {
        "Authorization": "Basic configured-in-header"
    }
    with pytest.raises((NotFoundError, ObjectDeletedError)):
        trace_server.obj_read(
            tsi.ObjReadReq(
                project_id=PROJECT_ID,
                object_id="support-agent-old",
                digest="latest",
            )
        )
    kept = trace_server.obj_read(
        tsi.ObjReadReq(
            project_id=PROJECT_ID,
            object_id="support-agent-kept",
            digest="latest",
        )
    ).obj
    assert kept.val["max_tokens"] == 4096
    assert kept.val["provider"] == provider.digest


def test_custom_runtime_apply_identical_replay_does_not_add_versions(
    trace_server,
) -> None:
    first = apply_runtime(trace_server)
    second = apply_runtime(trace_server)

    assert second == first
    objects = trace_server.objs_query(
        tsi.ObjQueryReq(
            project_id=PROJECT_ID,
            filter=tsi.ObjectVersionFilter(
                object_ids=["support-agent", "support-agent-support-v12"]
            ),
        )
    ).objs
    assert len(objects) == 2


def test_custom_runtime_apply_allows_an_empty_runtime_id_list(trace_server) -> None:
    apply_runtime(trace_server)

    result = apply_runtime(trace_server, runtime_ids=[])

    assert result.runtime_ids == []
    with pytest.raises((NotFoundError, ObjectDeletedError)):
        trace_server.obj_read(
            tsi.ObjReadReq(
                project_id=PROJECT_ID,
                object_id="support-agent-support-v12",
                digest="latest",
            )
        )


def test_custom_runtime_apply_objects_work_with_existing_completion_lookup(
    trace_server,
) -> None:
    class UnexpectedSecretFetcher:
        def fetch(self, secret_name: str) -> dict[str, dict[str, str]]:
            raise AssertionError(f"unexpected secret lookup: {secret_name}")

    apply_runtime(
        trace_server,
        api_key_secret=None,
        headers={"X-Auth": "configured-in-header"},
    )
    token = _secret_fetcher_context.set(UnexpectedSecretFetcher())
    try:
        provider_info = get_custom_provider_info(
            project_id=PROJECT_ID,
            provider_name="support-agent",
            model_name="support-agent-support-v12",
            obj_read_func=trace_server.obj_read,
        )
    finally:
        _secret_fetcher_context.reset(token)

    assert provider_info.base_url == "https://agent.example.com/v1"
    assert provider_info.api_key is None
    assert provider_info.extra_headers == {"X-Auth": "configured-in-header"}
    assert provider_info.actual_model_name == "support-v12"


@pytest.mark.parametrize(
    "request_data",
    [
        {"runtime_name": "", "runtime_ids": [{"id": "runtime"}]},
        {"runtime_name": "name::part", "runtime_ids": [{"id": "runtime"}]},
        {"runtime_name": "a" * 129, "runtime_ids": [{"id": "runtime"}]},
        {"runtime_name": "runtime", "runtime_ids": [{"id": ""}]},
        {
            "runtime_name": "runtime",
            "runtime_ids": [{"id": "duplicate"}, {"id": "duplicate"}],
        },
        {
            "runtime_name": "r" * 64,
            "runtime_ids": [{"id": "i" * 64}],
        },
    ],
)
def test_custom_runtime_apply_validates_names_before_writes(
    request_data: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        tsi.CustomRuntimeApplyReq(
            project_id=PROJECT_ID,
            base_url="https://agent.example.com/v1",
            **request_data,
        )


def test_custom_runtime_apply_rejects_sanitized_name_collision(trace_server) -> None:
    existing = Provider(
        name="support/agent",
        base_url="https://agent.example.com/v1",
        api_key_name="",
    )
    trace_server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=PROJECT_ID,
                object_id="support_agent",
                val=existing.model_dump(),
                builtin_object_class="Provider",
            )
        )
    )

    with pytest.raises(InvalidRequest) as exc_info:
        trace_server.custom_runtime_apply(
            tsi.CustomRuntimeApplyReq(
                project_id=PROJECT_ID,
                runtime_name="support:agent",
                base_url="https://agent.example.com/v1",
                runtime_ids=[],
            )
        )
    error = handle_server_exception(exc_info.value)
    assert error.status_code == 400


def test_custom_runtime_apply_rejects_sanitized_id_collision_before_writes(
    trace_server,
) -> None:
    with pytest.raises(InvalidRequest):
        apply_runtime(
            trace_server,
            runtime_ids=[
                tsi.CustomRuntimeID(id="model/a"),
                tsi.CustomRuntimeID(id="model:a"),
            ],
        )

    with pytest.raises(NotFoundError):
        trace_server.obj_read(
            tsi.ObjReadReq(
                project_id=PROJECT_ID,
                object_id="support-agent",
                digest="latest",
            )
        )


def test_custom_runtime_apply_does_not_claim_an_unrelated_provider_model(
    trace_server,
) -> None:
    other_provider = Provider(
        name="other",
        base_url="https://other.example.com/v1",
        api_key_name="",
    )
    other_provider_result = trace_server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=PROJECT_ID,
                object_id="other",
                val=other_provider.model_dump(),
                builtin_object_class="Provider",
            )
        )
    )
    unrelated_model = ProviderModel(
        name="support-v12",
        provider=other_provider_result.digest,
        max_tokens=2048,
    )
    trace_server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=PROJECT_ID,
                object_id="support-agent-support-v12",
                val=unrelated_model.model_dump(),
                builtin_object_class="ProviderModel",
            )
        )
    )

    with pytest.raises(InvalidRequest):
        apply_runtime(trace_server)

    stored_model = trace_server.obj_read(
        tsi.ObjReadReq(
            project_id=PROJECT_ID,
            object_id="support-agent-support-v12",
            digest="latest",
        )
    ).obj
    assert stored_model.val["provider"] == other_provider_result.digest


def test_custom_runtime_apply_retry_reconciles_models_from_old_provider_digest(
    trace_server,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_runtime(
        trace_server,
        runtime_ids=[
            tsi.CustomRuntimeID(id="remove-me"),
            tsi.CustomRuntimeID(id="keep-me"),
        ],
    )
    internal_server = trace_server._internal_trace_server
    real_obj_create = internal_server.obj_create
    create_count = 0

    def fail_after_provider(req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        nonlocal create_count
        create_count += 1
        if create_count == 2:
            raise RuntimeError("simulated model write failure")
        return real_obj_create(req)

    monkeypatch.setattr(internal_server, "obj_create", fail_after_provider)
    with pytest.raises(RuntimeError, match="simulated model write failure"):
        apply_runtime(
            trace_server,
            base_url="https://agent.example.com/v2",
            runtime_ids=[tsi.CustomRuntimeID(id="keep-me", max_tokens=8192)],
        )

    preserved_after_failure = trace_server.obj_read(
        tsi.ObjReadReq(
            project_id=PROJECT_ID,
            object_id="support-agent-remove-me",
            digest="latest",
        )
    ).obj
    assert preserved_after_failure.val["name"] == "remove-me"

    monkeypatch.setattr(internal_server, "obj_create", real_obj_create)
    apply_runtime(
        trace_server,
        base_url="https://agent.example.com/v2",
        runtime_ids=[tsi.CustomRuntimeID(id="keep-me", max_tokens=8192)],
    )

    with pytest.raises((NotFoundError, ObjectDeletedError)):
        trace_server.obj_read(
            tsi.ObjReadReq(
                project_id=PROJECT_ID,
                object_id="support-agent-remove-me",
                digest="latest",
            )
        )
