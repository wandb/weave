import json
import typing

from .. import api as weave
from .. import file_base


def load_jsonl(jsonlfile):
    rows = []
    for row in jsonlfile:
        rows.append(json.loads(row))
    return rows


@weave.op(
    name="file-refine_readjsonl",
    hidden=True,
    input_type={"self": file_base.FileBaseType(extension=weave.types.literal("jsonl"))},
)
def refine_readjsonl(self) -> weave.types.Type:
    with self.open() as f:
        return weave.types.TypeRegistry.type_of(load_jsonl(f))


@weave.op(
    name="file-readjsonl",
    input_type={"self": file_base.FileBaseType(extension=weave.types.literal("jsonl"))},
    output_type=weave.types.List(weave.types.TypedDict({})),
    refine_output_type=refine_readjsonl,
)
def readjsonl(self):
    with self.open() as f:
        return load_jsonl(f)


@weave.op()
def json_dumps(data: typing.Any) -> str:
    return json.dumps(data)
