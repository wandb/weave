import huggingface_hub
import datasets
import typing

import weave


class HFDatasetInfoTypedDict(typing.TypedDict):
    id: str
    lastModified: str
    tags: list[str]
    description: str
    # citation: str
    # sha: str
    # downloads: int


@weave.op(render_info={"type": "function"})
def hf_datasets() -> list[HFDatasetInfoTypedDict]:
    api = huggingface_hub.HfApi()
    return [
        {
            "id": dataset_info.id,
            "lastModified": dataset_info.lastModified,
            "tags": dataset_info.tags or [],
            "description": dataset_info.description,
            # "downloads": dataset_info.downloads,
        }
        for dataset_info in api.list_datasets()
    ]


# TODO: we really need finer grained numeric types!
def hf_feature_type_to_type(type_):
    if isinstance(type_, dict):
        prop_types = {}
        for key, type_ in type_.items():
            prop_types[key] = hf_feature_type_to_type(type_)
        return weave.types.TypedDict(prop_types)
    elif isinstance(type_, datasets.features.features.Sequence):
        return weave.types.List(hf_feature_type_to_type(type_.feature))
    elif isinstance(type_, datasets.features.features.Image):
        return weave.ops.PILImageType()
    elif isinstance(type_, datasets.features.features.ClassLabel):
        # TODO: this should be a classes type!!!!!
        return weave.types.Int()
    else:
        dtype = type_.dtype
        if dtype == "int8":
            return weave.types.Int()
        elif dtype == "int16":
            return weave.types.Int()
        elif dtype == "int32":
            return weave.types.Int()
        elif dtype == "int64":
            return weave.types.Int()
        elif dtype == "float32":
            return weave.types.Float()
        elif dtype == "string":
            return weave.types.String()
    raise weave.errors.WeaveTypeError("unhandled hf type: %s" % type_)


@weave.op(render_info={"type": "function"}, hidden=True)
def dataset_refine_output_type(name: str) -> weave.types.Type:
    ds = datasets.load_dataset(name, split="train", streaming=True)
    prop_types = {}
    for key, type_ in ds.features.items():
        prop_types[key] = hf_feature_type_to_type(type_)
    return weave.types.List(weave.types.TypedDict(prop_types))


@weave.op(
    render_info={"type": "function"},
    output_type=weave.types.List(weave.types.TypedDict({})),
    refine_output_type=dataset_refine_output_type,
)
def dataset(name: str):
    ds = datasets.load_dataset(name, split="train", streaming=True)

    rows = []
    for _, row in zip(range(100), iter(ds)):
        rows.append(row)
    return rows
