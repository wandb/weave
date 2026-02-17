import json
import logging
import sys
from collections.abc import Callable
from typing import Any

import pytest
from spec import SerializationTestCase
from test_cases import cases

import weave
from weave.trace.refs import ObjectRef
from weave.trace_server.trace_server_interface import (
    CallReadReq,
    FileContentReadReq,
    FileCreateReq,
    ObjCreateReq,
    ObjReadReq,
)
from weave.utils.project_id import to_project_id

"""
IMPORTANT RULES: Once a SerializationTestCase is created, it should never be modified.
As the code base evolves, it is expected that some of these test cases will break (since
the serialization format changes, op code changes, etc...). In such cases:
1. Copy the failing test case to a new test case.
2. Set the is_legacy flag to True on the new test case.
3. Rerun the test: this should PASS. If it does not, then it means you have made a
backwards incompatible change and data written by older clients will not be able to
be deserialized by newer clients.
4. Now you can modify the original test case to pass.

This methodology allows us to lock in the legacy serialization formats as a contact,
independent of the actual code that is used to serialize the data.
"""


def _maybe_close(obj: Any) -> None:
    close = getattr(obj, "close", None)
    if callable(close):
        close()


@pytest.fixture
def set_weave_logger_to_debug():
    logger = logging.getLogger("weave")
    current_level = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        yield
    finally:
        logger.setLevel(current_level)


@pytest.mark.parametrize(
    "case",
    cases,
    ids=lambda case: case.id,
)
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_serialization_correctness(
    client, case: SerializationTestCase, set_weave_logger_to_debug
):
    # Skip image test on macOS - PIL/Pillow produces different PNG encoding on macOS vs Linux
    # resulting in different file digests. This is expected behavior, not a bug.
    if sys.platform == "darwin" and case.id == "image":
        pytest.skip("Image encoding differs on macOS vs Linux")
    # Since code serialization changes pretty significantly between versions, we will assume
    # legacy for anything other than the latest python version
    is_legacy = case.is_legacy
    if case.python_version_code_capture:
        is_legacy = is_legacy or (
            sys.version_info.major != case.python_version_code_capture[0]
            or sys.version_info.minor != case.python_version_code_capture[1]
        )

    project_id = client._project_id()

    def verify_test_case():
        # Verify that all refs in json and objects are in objects.
        # verify that all files in json and objects are in files.
        found_refs = set()
        found_files = set()

        def ref_visitor(path: list[str | int], obj: Any):
            if isinstance(obj, str):
                try:
                    ref = ObjectRef.parse_uri(obj)
                    found_refs.add(obj)
                except (ValueError, TypeError):
                    pass

        def file_visitor(path: list[str | int], obj: Any):
            if isinstance(obj, dict) and "files" in obj:
                files = obj["files"]
                if isinstance(files, dict):
                    for file_digest in files.values():
                        found_files.add(file_digest)

        payload = [
            case.exp_json,
            case.exp_objects,
            case.exp_files,
        ]
        json_visitor(payload, ref_visitor)
        json_visitor(payload, file_visitor)

        for found_ref in found_refs:
            ref = ObjectRef.parse_uri(found_ref)
            entity = ref.entity
            project = ref.project
            name = ref.name
            digest = ref.digest
            found_project_id = to_project_id(entity, project)
            assert project_id == found_project_id

            for obj in case.exp_objects:
                if obj["object_id"] == name and obj["digest"] == digest:
                    break
            else:
                possible_obj = client.server.obj_read(
                    ObjReadReq(
                        project_id=project_id,
                        object_id=name,
                        digest=digest,
                    )
                )
                possible_val = possible_obj.obj.val
                exp_obj_dict = {
                    "object_id": name,
                    "digest": digest,
                    "exp_val": possible_val,
                }
                print(f"Possible object:\n{json.dumps(exp_obj_dict, indent=2)}")
                raise ValueError(
                    f"Ref {found_ref} was not found in the expected objects, please add it to the expected objects"
                )

        for found_file in found_files:
            for exp_file in case.exp_files:
                if exp_file["digest"] == found_file:
                    break
            else:
                possible_file = client.server.file_content_read(
                    FileContentReadReq(
                        project_id=project_id,
                        digest=found_file,
                    )
                )
                possible_content = possible_file.content
                print(f"""Possible file:
                {{
                    "digest": "{found_file}",
                    "exp_content": {possible_content},
                }}
                """)
                raise ValueError(
                    f"File {found_file} was not found in the expected files, please add it to the expected files"
                )

    def seed_legacy_data():
        # This method will seed the database with the expected objects and files
        # It should only be called if is_legacy is True.

        if not is_legacy:
            raise ValueError("is_legacy is False")

        if case.exp_objects:
            for obj in case.exp_objects:
                obj_res = client.server.obj_create(
                    ObjCreateReq(
                        obj={
                            "project_id": project_id,
                            "object_id": obj["object_id"],
                            "val": obj["exp_val"],
                        }
                    )
                )

                # Assert that the generated digest matches the one provided in the test case
                # If this assert triggers, there are a couple of ways to fix it:
                #  1) least intrusive: update the test case
                #  2) more intrusive: obj_create could be updated to allow the caller to pass in a digest that would override the generated one
                assert obj_res.digest == obj["digest"]

        if case.exp_files:
            for file in case.exp_files:
                file_res = client.server.file_create(
                    FileCreateReq(
                        project_id=project_id,
                        name="name",
                        content=file["exp_content"],
                    )
                )
                assert file_res.digest == file["digest"]

    def test_publish_flow():
        # This method will assert that the publish flow works as expected.
        # Specifically, we will publish the object, assert that it can be
        # deserialized using the ref-get pattern, and finally, assert that
        # the expected objects and files are created in the database.

        runtime_object = None
        gotten_obj = None
        try:
            runtime_object = case.runtime_object_factory()

            # If we are in legacy mode, then we just publish the expected json directly.
            if is_legacy:
                published_obj = weave.publish(case.exp_json)
            else:
                published_obj = weave.publish(runtime_object)
            digest = published_obj.digest
            gotten_obj = weave.get(published_obj.uri())
            assert case.equality_check(gotten_obj, runtime_object)

            # Verify the correct JSON is stored in the database.
            res = client.server.obj_read(
                ObjReadReq(
                    project_id=project_id,
                    object_id=published_obj.name,
                    digest=published_obj.digest,
                )
            )
            val = res.obj.val
            print(f"Found object json:\n{json.dumps(val, indent=2)}")
            assert val == case.exp_json

            # Check expected support objects and files
            if case.exp_objects:
                for obj in case.exp_objects:
                    obj_res = client.server.obj_read(
                        ObjReadReq(
                            project_id=project_id,
                            object_id=obj["object_id"],
                            digest=obj["digest"],
                        )
                    )
                    assert obj_res.obj.val == obj["exp_val"]

            if case.exp_files:
                for file in case.exp_files:
                    file_res = client.server.file_content_read(
                        FileContentReadReq(
                            project_id=project_id,
                            digest=file["digest"],
                        )
                    )
                    assert file_res.content == file["exp_content"]
        finally:
            _maybe_close(gotten_obj)
            _maybe_close(runtime_object)

    def test_input_flow():
        # This method will assert that the input flow works as expected.
        # Specifically, when the value is used as an input, does it get
        # correctly serialized and deserialized by the client reader.

        runtime_object = None
        gotten_obj = None
        try:
            runtime_object = case.runtime_object_factory()

            @weave.op
            def func(val):
                return val

            # Similarly to the publish flow, if we are in legacy mode, then we just
            # use the expected json directly.
            if is_legacy:
                val = case.exp_json
            else:
                val = runtime_object

            func(val)
            client.flush()
            calls = func.calls()
            assert len(calls) == 1
            calls_0 = calls[0]
            call_id = calls_0.id
            gotten_obj = calls_0.inputs["val"]

            assert case.equality_check(gotten_obj, runtime_object)

            # Verify the correct JSON is stored in the database
            res = client.server.call_read(
                CallReadReq(
                    project_id=project_id,
                    id=call_id,
                )
            )

            # If we are not inline, then the value is expected to be a Ref
            # and we need to read it from the database.
            if not case.inline_call_param and not is_legacy:
                ref = ObjectRef.parse_uri(res.call.inputs["val"])
                res = client.server.obj_read(
                    ObjReadReq(
                        project_id=project_id,
                        object_id=ref.name,
                        digest=ref.digest,
                    )
                )
                val = res.obj.val
            else:
                val = res.call.inputs["val"]

            assert val == case.exp_json
        finally:
            _maybe_close(gotten_obj)
            _maybe_close(runtime_object)

    if is_legacy:
        seed_legacy_data()

    test_publish_flow()
    test_input_flow()

    # We put this last so that helper functions can report more useful error messages
    # based on true data in the database.
    verify_test_case()


def json_visitor(
    obj: Any,
    visitor: Callable[[list[str | int], Any], None],
):
    def _json_visitor(
        obj: Any,
        visitor: Callable[[list[str | int], Any], None],
        path: list[str | int],
    ):
        visitor(path, obj)

        if isinstance(obj, dict):
            for k, v in obj.items():
                _json_visitor(v, visitor, path + [k])
        elif isinstance(obj, list):
            for ndx, v in enumerate(obj):
                _json_visitor(v, visitor, path + [ndx])

    _json_visitor(obj, visitor, [])
