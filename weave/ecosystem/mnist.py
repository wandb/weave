# Mnist dataset example
#
# TODO:
#   - Doesn't use the much faster ArrowWeaveList

import typing
import weave
from weave import panels
import PIL.Image

from torchvision import datasets


class MnistExample(typing.TypedDict):
    image: PIL.Image.Image  # TODO: size constraints
    label: int  # TODO: enum?


# TODO: How is this better than TypedDict? we can attach ops... but... is that better?
@weave.type()
class MnistSplits:
    train: list[MnistExample]
    test: list[MnistExample]

    @weave.op()
    def get_train(self) -> list[MnistExample]:
        return self.train

    @weave.op()
    def get_test(self) -> list[MnistExample]:
        return self.test


# TODO: inherit from base Dataset
@weave.type()
class MnistDataset:
    name: str
    description: str
    data: MnistSplits

    @weave.op()
    def get_data(self) -> MnistSplits:
        return self.data


@weave.op(render_info={"type": "function"})
# TODO: 0-argument functions don't work in WeaveJS at the moment
def mnist(limit: int = -1) -> MnistDataset:
    torch_mnist_train = datasets.MNIST(".", train=True, download=True)
    mnist_train = []
    for im, label in list(torch_mnist_train)[:limit]:
        mnist_train.append(MnistExample(image=im, label=label))

    torch_mnist_test = datasets.MNIST(".", train=False, download=True)
    mnist_test = []
    for im, label in list(torch_mnist_test)[:limit]:
        mnist_test.append(MnistExample(image=im, label=label))

    return MnistDataset(
        name="MNIST",
        description="The famous MNIST dataset",
        data=MnistSplits(mnist_train, mnist_test),
    )


# TODO: This should be generic
@weave.op()
def mnist_dataset_card(dataset: MnistDataset) -> panels.Card:
    return panels.Card(
        title=dataset.name,
        subtitle="",
        content=[
            panels.CardTab(
                name="Overview",
                content=panels.Group(
                    items=[
                        panels.LabeledItem(
                            item=dataset.description, label="Description"
                        ),
                    ]
                ),
            ),
            panels.CardTab(
                name="Limitations & Use",
                content=panels.LabeledItem(item="tab2", label="tab2-label"),
            ),
            # TODO: show both splits in a Data panel with a drop down picker
            panels.CardTab(
                name="Train split",
                content=panels.LabeledItem(
                    item=dataset.get_data().get_train(), height=500, label="Train split"
                ),
            ),
            panels.CardTab(
                name="Test split",
                content=panels.LabeledItem(
                    item=dataset.get_data().get_test(), height=500, label="Test split"
                ),
            ),
        ],
    )
