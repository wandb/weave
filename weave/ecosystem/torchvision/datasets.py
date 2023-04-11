# Torch vision datasets
#
# TODO:
#   - Doesn't use the much faster ArrowWeaveList
#   - The patterns here aren't final. Prefer the style used in huggingface/models

from typing import TypeVar
import typing
import weave
from weave import infer_types
from weave import panels
import PIL.Image

from torchvision import datasets


ExampleType = TypeVar("ExampleType")


class TypedDictAny(typing.TypedDict):
    pass


class TorchVisionDataset(typing.TypedDict):
    name: str
    description: str
    data: dict[str, list[TypedDictAny]]


def make_torchvision_splits(
    dataset_fn, limit, split_specs, example_keys, example_constructor
) -> dict:
    splits = {}
    for split_name, dataset_fn_kwargs in split_specs:
        raw_data = dataset_fn(".", download=True, **dataset_fn_kwargs)
        examples = []
        for _, row in zip(range(limit), raw_data):
            example = example_constructor(**dict(zip(example_keys, row)))
            examples.append(example)
        splits[split_name] = examples
    return splits


@weave.op(
    input_type={
        "dataset": weave.types.Function(
            {}, infer_types.python_type_to_type(TorchVisionDataset)
        )
    }
)
def torch_vision_dataset_card(dataset) -> panels.Card:
    # TODO: split should be chosen from dropdown rather than via tab.
    #   - or ideally, it should look like one big table with a "split" column.
    dataset_type = dataset.type
    splits_type = dataset_type.property_types["data"]
    split_names = splits_type.property_types.keys()
    split_tabs = []
    for split_name in split_names:
        split_data = dataset["data"][split_name]
        split_tabs.append(
            panels.CardTab(
                name=f"{split_name} split",
                content=panels.LabeledItem(
                    item=split_data, height=500, label=f"{split_name} split"
                ),
            ),
        )
    return panels.Card(
        title=dataset["name"],
        subtitle="",
        content=[
            panels.CardTab(
                name="Overview",
                content=panels.Group(
                    items={
                        "description": panels.LabeledItem(
                            item=dataset["description"], label="Description"
                        ),
                    }
                ),
            ),
            panels.CardTab(
                name="Limitations & Use",
                content=panels.LabeledItem(item="tab2", label="tab2-label"),
            ),
            *split_tabs,
        ],
    )


class ImageLabelExample(typing.TypedDict):
    image: PIL.Image.Image  # TODO: size constraints
    label: int  # TODO: enum?


class MnistSplits(typing.TypedDict):
    train: list[ImageLabelExample]
    test: list[ImageLabelExample]


class MnistDataset(TorchVisionDataset):
    data: MnistSplits  # type: ignore


@weave.op(render_info={"type": "function"})
# TODO: 0-argument functions don't work in WeaveJS at the moment
def mnist(limit: int = -1) -> MnistDataset:
    return MnistDataset(
        name="MNIST",
        description="The famous MNIST dataset",
        data=MnistSplits(  # type: ignore
            make_torchvision_splits(
                datasets.MNIST,
                limit,
                [("train", {"train": True}), ("test", {"train": False})],
                ("image", "label"),
                ImageLabelExample,
            )
        ),
    )


class Food101Splits(typing.TypedDict):
    train: list[ImageLabelExample]
    test: list[ImageLabelExample]


class Food101Dataset(TorchVisionDataset):
    data: Food101Splits  # type: ignore


@weave.op(render_info={"type": "function"})
# TODO: 0-argument functions don't work in WeaveJS at the moment
def food101(limit: int = -1) -> Food101Dataset:
    return Food101Dataset(
        name="Food101",
        description="The Food-101 is a challenging data set of 101 food categories, with 101’000 images. For each class, 250 manually reviewed test images are provided as well as 750 training images. On purpose, the training images were not cleaned, and thus still contain some amount of noise. This comes mostly in the form of intense colors and sometimes wrong labels. All images were rescaled to have a maximum side length of 512 pixels.",
        data=Food101Splits(  # type: ignore
            make_torchvision_splits(
                datasets.Food101,
                limit,
                [("train", {"split": "train"}), ("test", {"split": "test"})],
                ("image", "label"),
                ImageLabelExample,
            )
        ),
    )
