import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypedDict, Union

import pytest
from PIL import Image

import weave
from weave.trace.refs import ObjectRef
from weave.trace_server.trace_server_interface import (
    CallReadReq,
    FileContentReadReq,
    FileCreateReq,
    ObjCreateReq,
    ObjReadReq,
)

"""
# Data Type Directory (Test Checklist)

## Primitives:
[x] int
[x] float
[x] str
[x] bool
[x] None

## Primitive Containers:
[x] list
[x] dict
[] tuple
[] set

## Media Types:
[] Audio
[] Content
[x] Datetime
[] File
[x] Image
[x] Markdown
[] Video

## Container Types:
[] Dataclass
[] Pydantic BaseModel

## Weave Core Types:
[] Op
[] Object

## Weave Library Objects:
[] Model
[] Scorer
[] Evaluation
[] Dataset
[] Prompt

### Weave Library Specialized Objects:
[] LLMStructuredCompletionModel
[] LLMAsAJudgeScorer

## Weave Config Objects:
[] AnnotationSpec
[] Leaderboard
[] SavedView
[] Monitor
"""

def default_equality_check(a, b):
    return a == b


class ExpFileSpec(TypedDict):
    digest: str
    exp_content: str


class ExpObjectSpec(TypedDict):
    object_id: str
    digest: str
    exp_val: dict


@dataclass
class SerializationTestCase:
    # A unique identifier for the test case
    id: str

    # Returns a python object to be serialized
    runtime_object_factory: Callable[[], Any]

    # If true, then then used in a paramter/return value of a call,
    # will be directly stored in the call's inputs/outputs (as opposed
    # to being published and stored as a Ref)
    inline_call_param: bool

    # The expected json representation of the object
    exp_json: dict

    # The published objects that are expected to have been created
    # and used to support the serialization
    exp_objects: list[ExpObjectSpec]

    # The associated files that are expected to have been created
    # and used to support the serialization
    exp_files: list[ExpFileSpec]

    # If true, then the current library code is not expected to PRODUCE
    # this JSON, but should still be able to deserialize it. When True,
    # we will bootstrap the expected objects and files and assert that
    # deserialization still works.
    is_legacy: bool

    # A function that checks if two objects are equal. If None, then
    # the objects are expected to be equal using `==`
    equality_check: Optional[Callable[[Any, Any], bool]] = default_equality_check


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
@pytest.mark.parametrize(
    "case",
    [
        # Primitives
        SerializationTestCase(
            id="primitives",
            runtime_object_factory=lambda: {
                "int": 1,
                "float": 1.0,
                "str": "hello",
                "bool": True,
                "none": None,
                "list": [1, 2, 3],
            },
            inline_call_param=True,
            is_legacy=False,
            exp_json={
                "int": 1,
                "float": 1.0,
                "str": "hello",
                "bool": True,
                "none": None,
                "list": [1, 2, 3],
            },
            exp_objects=[],
            exp_files=[],
        ),
        # Datetime
        SerializationTestCase(
            id="datetime",
            runtime_object_factory=lambda: datetime(
                2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc
            ),
            inline_call_param=True,
            is_legacy=False,
            exp_json={
                "_type": "CustomWeaveType",
                "load_op": "weave:///shawn/test-project/op/load_datetime.datetime:vBlX1uTKCGWJCbt7bmYHsvnse0lidjCeSGVQjE44Evc",
                "val": "2025-01-01T00:00:00+00:00",
                "weave_type": {"type": "datetime.datetime"},
            },
            exp_objects=[
                {
                    "object_id": "load_datetime.datetime",
                    "digest": "vBlX1uTKCGWJCbt7bmYHsvnse0lidjCeSGVQjE44Evc",
                    "exp_val": {
                        "_type": "CustomWeaveType",
                        "weave_type": {"type": "Op"},
                        "files": {
                            "obj.py": "ncV0DfMpJ6gN2ls9iSpQwSiYplvhm8CO2ZDNqjPbdBg"
                        },
                    },
                }
            ],
            exp_files=[
                {
                    "digest": "ncV0DfMpJ6gN2ls9iSpQwSiYplvhm8CO2ZDNqjPbdBg",
                    "exp_content": b'import weave\nimport datetime\n\n@weave.op()\ndef load(encoded: str) -> datetime.datetime:\n    """Deserialize an ISO format string back to a datetime object with timezone."""\n    return datetime.datetime.fromisoformat(encoded)\n',
                }
            ],
        ),
        # Markdown:
        SerializationTestCase(
            id="markdown",
            runtime_object_factory=lambda: weave.Markdown("# Hello, world!"),
            inline_call_param=True,
            is_legacy=False,
            exp_json={
                "_type": "CustomWeaveType",
                "load_op": "weave:///shawn/test-project/op/load_rich.markdown.Markdown:ZJrNtY2McTqdAZdfBmciQV1TyCouPS8ED400FQFE4JE",
                "val": {"code_theme": "monokai", "markup": "# Hello, world!"},
                "weave_type": {"type": "rich.markdown.Markdown"},
            },
            exp_objects=[
                {
                    "object_id": "load_rich.markdown.Markdown",
                    "digest": "ZJrNtY2McTqdAZdfBmciQV1TyCouPS8ED400FQFE4JE",
                    "exp_val": {
                        "_type": "CustomWeaveType",
                        "weave_type": {"type": "Op"},
                        "files": {
                            "obj.py": "zunYz3rpUk5IkwbglUHXBJFszhSKvtLIftOGvMp4xFo"
                        },
                    },
                }
            ],
            exp_files=[
                {
                    "digest": "zunYz3rpUk5IkwbglUHXBJFszhSKvtLIftOGvMp4xFo",
                    "exp_content": b"import weave\nfrom typing import TypedDict\nfrom typing import NotRequired\nfrom rich.markdown import Markdown\n\nclass SerializedMarkdown(TypedDict):\n    markup: str\n    code_theme: NotRequired[str]\n\n@weave.op()\ndef load(encoded: SerializedMarkdown) -> Markdown:\n    return Markdown(**encoded)\n",
                }
            ],
            equality_check=lambda a, b: a.markup == b.markup
            and a.code_theme == b.code_theme,
        ),
        # Image (PIL.Image.Image)
        SerializationTestCase(
            id="image",
            runtime_object_factory=lambda: Image.new("RGB", (10, 10), "red"),
            inline_call_param=True,
            is_legacy=False,
            exp_json={
                "_type": "CustomWeaveType",
                "weave_type": {"type": "PIL.Image.Image"},
                "files": {"image.png": "Ac3YO5daeesZTxBfXf7DAKaQZ5IZysk2HvclN8sfwxQ"},
                "load_op": "weave:///shawn/test-project/op/load_PIL.Image.Image:XTwpuNcfNiGtjAaWpDPfMSflzS7JYxJNd6FYk1TAfeA",
            },
            exp_objects=[
                {
                    "object_id": "load_PIL.Image.Image",
                    "digest": "XTwpuNcfNiGtjAaWpDPfMSflzS7JYxJNd6FYk1TAfeA",
                    "exp_val": {
                        "_type": "CustomWeaveType",
                        "weave_type": {"type": "Op"},
                        "files": {
                            "obj.py": "ReUEgimaLvoco8RMDnTr4tTo26SXYwVz61tJHoDJ1CI"
                        },
                    },
                }
            ],
            exp_files=[
                {
                    "digest": "ReUEgimaLvoco8RMDnTr4tTo26SXYwVz61tJHoDJ1CI",
                    "exp_content": b'import weave\nfrom weave.trace.serialization.mem_artifact import MemTraceFilesArtifact\nfrom weave.utils.iterators import first\nimport PIL.Image as Image\n\n@weave.op()\ndef load(artifact: MemTraceFilesArtifact, name: str) -> Image.Image:\n    # Today, we assume there can only be 1 image in the artifact.\n    filename = first(artifact.path_contents)\n    if not filename.startswith("image."):\n        raise ValueError(f"Expected filename to start with \'image.\', got {filename}")\n\n    path = artifact.path(filename)\n    return Image.open(path)\n',
                },
                {
                    "digest": "Ac3YO5daeesZTxBfXf7DAKaQZ5IZysk2HvclN8sfwxQ",
                    "exp_content": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x02\x00\x00\x00\x02PX\xea\x00\x00\x00\x12IDATx\x9cc\xfc\xcf\x80\x0f0\xe1\x95\x1d\xb1\xd2\x00A,\x01\x13\xb1\ns\x13\x00\x00\x00\x00IEND\xaeB`\x82",
                },
            ],
            equality_check=lambda a, b: a.tobytes() == b.tobytes(),
        ),
    ],
    ids=lambda case: case.id,
)
def test_serialization_compatability(client, case):
    if sys.version_info.major <= 3 and sys.version_info.minor <= 9:
        pytest.skip(
            "Skipping test for Python 3.9 and below due to inconsistent op code"
        )

    project_id = client._project_id()

    def verify_test_case():
        # Verify that all refs in json and objects are in objects.
        # verify that all files in json and objects are in files.
        found_refs = set()
        found_files = set()

        def ref_visitor(path: list[Union[str, int]], obj: Any):
            if isinstance(obj, str):
                try:
                    ref = ObjectRef.parse_uri(obj)
                    found_refs.add(obj)
                except ValueError:
                    pass

        def file_visitor(path: list[Union[str, int]], obj: Any):
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
            found_project_id = f"{entity}/{project}"
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

        if not case.is_legacy:
            raise ValueError("is_legacy is False")

        if case.exp_objects:
            for obj in case.exp_objects:
                obj_res = client.server.obj_create(
                    ObjCreateReq(
                        obj={
                            "project_id": project_id,
                            "object_id": obj["object_id"],
                            "digest": obj["digest"],
                            "val": obj["exp_val"],
                        }
                    )
                )
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

        runtime_object = case.runtime_object_factory()

        # If we are in legacy mode, then we just publish the expected json directly.
        if case.is_legacy:
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

    def test_input_flow():
        # This method will assert that the input flow works as expected.
        # Specifically, when the value is used as an input, does it get
        # correctly serialized and deserialized by the client reader.

        runtime_object = case.runtime_object_factory()

        @weave.op
        def func(val):
            return val

        # Similarly to the publish flow, if we are in legacy mode, then we just
        # use the expected json directly.
        if case.is_legacy:
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
        if not case.inline_call_param:
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

    if case.is_legacy:
        seed_legacy_data()

    test_publish_flow()
    test_input_flow()

    # We put this last so that helper functions can report more useful error messages
    # based on true data in the database.
    verify_test_case()


def json_visitor(
    obj: Any,
    visitor: Callable[[list[Union[str, int]], Any], None],
):
    def _json_visitor(
        obj: Any,
        visitor: Callable[[list[Union[str, int]], Any], None],
        path: list[Union[str, int]],
    ):
        visitor(path, obj)

        if isinstance(obj, dict):
            for k, v in obj.items():
                _json_visitor(v, visitor, path + [k])
        elif isinstance(obj, list):
            for ndx, v in enumerate(obj):
                _json_visitor(v, visitor, path + [ndx])

    _json_visitor(obj, visitor, [])
