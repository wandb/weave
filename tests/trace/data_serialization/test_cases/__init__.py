from datetime import datetime, timezone

from PIL import Image

import weave
from tests.trace.data_serialization.spec import SerializationTestCase
from tests.trace.data_serialization.test_cases.audio_cases import audio_cases

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
[X] Audio
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

cases = [
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
                    "files": {"obj.py": "ncV0DfMpJ6gN2ls9iSpQwSiYplvhm8CO2ZDNqjPbdBg"},
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
                    "files": {"obj.py": "zunYz3rpUk5IkwbglUHXBJFszhSKvtLIftOGvMp4xFo"},
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
                    "files": {"obj.py": "ReUEgimaLvoco8RMDnTr4tTo26SXYwVz61tJHoDJ1CI"},
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
    *audio_cases,
]
