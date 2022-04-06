import datasets as hf_datasets
import weave


class HFDatasetType(weave.types.ObjectType):
    name = "hf-dataset"

    def property_types(self):
        return {"name": weave.types.String()}


@weave.weave_class(weave_type=HFDatasetType)
class HFDataset:
    def __init__(self, name):
        self.name = name

    @weave.op(
        input_type={
            "self": HFDatasetType(),
        },
        output_type=weave.types.TypedDict(
            {
                "description": weave.types.String(),
                "homepage": weave.types.String(),
                "download_size": weave.types.Int(),
                "version": weave.types.String(),
            }
        ),
    )
    def info(self):
        dataset_builder = hf_datasets.load_dataset_builder(self.name)
        info = dataset_builder.info
        # TODO: this could use a mapper
        return {
            "description": info.description,
            "homepage": info.homepage,
            "download_size": info.download_size,
            "version": info.version,
        }


HFDatasetType.instance_classes = HFDataset
HFDatasetType.instance_class = HFDataset


@weave.op(input_type={}, output_type=weave.types.List(HFDatasetType()))
def datasets():
    return weave.List([HFDataset(name) for name in hf_datasets.list_datasets()])
