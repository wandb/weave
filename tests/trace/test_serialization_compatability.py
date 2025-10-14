from dataclasses import dataclass
from typing import Any, Callable, Optional, TypedDict

import pytest

import weave
from weave.trace.refs import ObjectRef
from weave.trace_server.trace_server_interface import (
    CallReadReq,
    FileContentReadReq,
    FileCreateReq,
    ObjCreateReq,
    ObjReadReq,
)


class ExpFileSpec(TypedDict):
    project_id: str
    digest: str
    exp_content: str


class ExpObjectSpec(TypedDict):
    project_id: str
    object_id: str
    digest: str
    exp_val: dict


@dataclass
class SerializationTestCase:
    runtime_object_factory: Callable[[], Any]
    inline_call_param: bool
    exp_json: dict
    exp_files: list[ExpFileSpec]
    exp_objects: list[dict]
    is_legacy: bool
    equality_check: Optional[Callable[[Any, Any], bool]] = None


@pytest.mark.parametrize(
    "case",
    [
        SerializationTestCase(
            runtime_object_factory=lambda: weave.Markdown("# Hello, world!"),
            inline_call_param=True,
            is_legacy=False,
            exp_json={
                "_type": "CustomWeaveType",
                "load_op": "weave:///shawn/test-project/op/load_rich.markdown.Markdown:7pXiY5MKlunK6ZXuczX5TOV4yafx1wkJBo2KCCy89cg",
                "val": {"code_theme": "monokai"},
                "weave_type": {"type": "rich.markdown.Markdown"},
                "files": {"content.md": "Va5jSOJXRyFLKL6k2R1YIZFL4wXvd6XZaFmySnMzkjA"},
            },
            exp_objects=[
                {
                    "project_id": "shawn/test-project",
                    "object_id": "load_rich.markdown.Markdown",
                    "digest": "7pXiY5MKlunK6ZXuczX5TOV4yafx1wkJBo2KCCy89cg",
                    "exp_val": {
                        "_type": "CustomWeaveType",
                        "weave_type": {"type": "Op"},
                        "files": {
                            "obj.py": "QihXk5eJKRNujgUxZuIGaiztB7j5VkrBpd681z4PeY8"
                        },
                        "val": None,
                    },
                }
            ],
            exp_files=[
                {
                    "project_id": "shawn/test-project",
                    "digest": "Va5jSOJXRyFLKL6k2R1YIZFL4wXvd6XZaFmySnMzkjA",
                    "exp_content": b"# Hello, world!",
                },
                {
                    "project_id": "shawn/test-project",
                    "digest": "QihXk5eJKRNujgUxZuIGaiztB7j5VkrBpd681z4PeY8",
                    "exp_content": b'import weave\nfrom typing import Any\nfrom rich.markdown import Markdown\n\n@weave.op()\ndef load(artifact: "MemTraceFilesArtifact", name: str, val: Any) -> Markdown:\n    """Load markdown from file and metadata."""\n    with artifact.open("content.md", binary=False) as f:\n        markup = f.read()\n\n    kwargs = {}\n    if val and isinstance(val, dict) and "code_theme" in val:\n        kwargs["code_theme"] = val["code_theme"]\n\n    return Markdown(markup=markup, **kwargs)\n',
                },
            ],
            equality_check=lambda a, b: a.markup == b.markup
            and a.code_theme == b.code_theme,
        ),
        SerializationTestCase(
            runtime_object_factory=lambda: weave.Markdown("# Hello, world!"),
            inline_call_param=True,
            is_legacy=True,
            exp_json={
                "_type": "CustomWeaveType",
                "load_op": "weave:///shawn/test-project/op/load_rich.markdown.Markdown:ZJrNtY2McTqdAZdfBmciQV1TyCouPS8ED400FQFE4JE",
                "val": {"code_theme": "monokai", "markup": "# Hello, world!"},
                "weave_type": {"type": "rich.markdown.Markdown"},
            },
            exp_objects=[
                {
                    "project_id": "shawn/test-project",
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
                    "project_id": "shawn/test-project",
                    "digest": "zunYz3rpUk5IkwbglUHXBJFszhSKvtLIftOGvMp4xFo",
                    "exp_content": b"import weave\nfrom typing import TypedDict\nfrom typing import NotRequired\nfrom rich.markdown import Markdown\n\nclass SerializedMarkdown(TypedDict):\n    markup: str\n    code_theme: NotRequired[str]\n\n@weave.op()\ndef load(encoded: SerializedMarkdown) -> Markdown:\n    return Markdown(**encoded)\n",
                }
            ],
            equality_check=lambda a, b: a.markup == b.markup
            and a.code_theme == b.code_theme,
        ),
    ],
)
def test_serialization_compatability(client, case):
    def seed_legacy_data():
        if not case.is_legacy:
            return

        if case.exp_objects:
            for obj in case.exp_objects:
                obj_res = client.server.obj_create(
                    ObjCreateReq(
                        obj={
                            "project_id": client._project_id(),
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
                        project_id=client._project_id(),
                        name="name",
                        content=file["exp_content"],
                    )
                )
                assert file_res.digest == file["digest"]

    def test_publish_flow():
        runtime_object = case.runtime_object_factory()
        if not case.is_legacy:
            published_obj = weave.publish(runtime_object)
        else:
            published_obj = weave.publish(case.exp_json)
        digest = published_obj.digest
        gotten_obj = weave.ref(published_obj.uri()).get()
        assert case.equality_check(gotten_obj, runtime_object)

        # Check low level data
        res = client.server.obj_read(
            ObjReadReq(
                project_id=client._project_id(),
                object_id=published_obj.name,
                digest=published_obj.digest,
            )
        )
        val = res.obj.val
        assert val == case.exp_json

        if case.exp_objects:
            for obj in case.exp_objects:
                obj_res = client.server.obj_read(
                    ObjReadReq(
                        project_id=client._project_id(),
                        object_id=obj["object_id"],
                        digest=obj["digest"],
                    )
                )
                assert obj_res.obj.val == obj["exp_val"]

        if case.exp_files:
            for file in case.exp_files:
                file_res = client.server.file_content_read(
                    FileContentReadReq(
                        project_id=client._project_id(),
                        digest=file["digest"],
                    )
                )
                assert file_res.content == file["exp_content"]

    def test_input_flow():
        runtime_object = case.runtime_object_factory()

        @weave.op
        def func(val):
            return val

        if not case.is_legacy:
            val = runtime_object
        else:
            val = case.exp_json

        func(val)
        client.flush()
        calls = func.calls()
        assert len(calls) == 1
        calls_0 = calls[0]
        call_id = calls_0.id
        gotten_obj = calls_0.inputs["val"]

        assert case.equality_check(gotten_obj, runtime_object)

        # Check low level data

        if not case.is_legacy:
            res = client.server.call_read(
                CallReadReq(
                    project_id=client._project_id(),
                    id=call_id,
                )
            )

            if not case.inline_call_param:
                ref = ObjectRef.parse_uri(res.call.inputs["val"])
                res = client.server.obj_read(
                    ObjReadReq(
                        project_id=client._project_id(),
                        object_id=ref.name,
                        digest=ref.digest,
                    )
                )
                val = res.obj.val
            else:
                val = res.call.inputs["val"]

            assert val == case.exp_json

    seed_legacy_data()
    test_publish_flow()
    test_input_flow()
