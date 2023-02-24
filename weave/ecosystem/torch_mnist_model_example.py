import dataclasses
import torch
from torch import nn
from torch import optim
from torch.utils.data import Dataset
from torchvision import transforms

import typing
import weave

from . import pytorch

from weave import context_state as _context


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


@dataclasses.dataclass(frozen=True)
class ModelType(weave.types.ObjectType):
    input_type: weave.types.Type = weave.types.Any()
    output_type: weave.types.Type = weave.types.Any()

    def property_types(self):
        # Huh... this has the same interface as any function...
        return {
            "input_type": self.input_type,
            "output_type": self.output_type,
            "pred_fn": pytorch.TorchModelType(),
        }


@weave.weave_class(weave_type=ModelType)
@dataclasses.dataclass()
class Model:
    input_type: weave.types.Type
    output_type: weave.types.Type

    pred_fn: torch.nn.Sequential  # just the torch model above for now

    @weave.op(
        input_type={
            "self": ModelType(),
            "X": lambda input_type: input_type["self"].input_type,
        },
        # TODO
        # output_type=lambda input_type: weave.types.List(
        #     weave.types.TypedDict(
        #         {
        #             "X": input_type["self"].input_type.object_type,
        #             "y": input_type["self"].output_type.object_type,
        #         }
        #     )
        # ),
        # I hardcoded the output_type of predict and train just to show the example
        # working.
        output_type=weave.types.List(
            weave.types.TypedDict(
                {
                    "X": weave.ops.image.PILImageType(),  # type: ignore
                    "y": weave.types.Int(),
                }
            )
        ),
    )
    def predict(self, X):
        # Note, this is a copy of the transform in TorchMnistDataset!
        transform = transforms.Compose(
            [transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))]
        )
        inputs = [transform(x) for x in X]
        class_preds = self.pred_fn(torch.stack(inputs))
        _, final_preds = torch.max(class_preds.data, 1)
        final_preds = final_preds.tolist()
        # TODO: do a faster column-oriented version
        rows = []
        for x, y in zip(X, final_preds):
            rows.append({"X": x, "y": y})
        return rows


ModelType.instance_class = Model
ModelType.instance_classes = Model


class TorchMnistTrainConfig(typing.TypedDict):
    fc_layer_size: int
    dropout: float
    epochs: int
    learning_rate: float
    batch_size: int


class TorchMnistDataset(Dataset):
    transform = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))]
    )

    def __init__(self, X, y):
        self.X = X
        self.y = y

    def __len__(self):
        return len(self.X)

    def __getitem__(self, i):
        return self.transform(self.X[i]), self.y[i]


def build_network(fc_layer_size, dropout):
    network = nn.Sequential(  # fully-connected, single hidden layer
        nn.Flatten(),
        nn.Linear(784, fc_layer_size),
        nn.ReLU(),
        nn.Dropout(dropout),
        nn.Linear(fc_layer_size, 10),
        nn.LogSoftmax(dim=1),
    )
    return network.to(DEVICE)


def train_epoch(network, loader, optimizer):
    cumu_loss = 0
    for _, (data, target) in enumerate(loader):
        data, target = data.to(DEVICE), target.to(DEVICE)
        optimizer.zero_grad()
        loss = nn.functional.nll_loss(network(data), target)
        cumu_loss += loss.item()
        loss.backward()
        optimizer.step()
    return cumu_loss / len(loader)


@weave.op(
    render_info={"type": "function"},
    input_type={
        "X": weave.types.List(weave.ops.image.PILImageType()),  # type: ignore
        "y": weave.types.List(weave.types.Int()),  # TODO: class enum?
    },
    # TODO: WeaveJS doesn't support callable output type yet.
    # output_type=lambda input_type: ModelType(input_type["X"], input_type["y"]),
    output_type=ModelType(),
)
def train(X, y, config: TorchMnistTrainConfig):
    loader = torch.utils.data.DataLoader(
        TorchMnistDataset(X, y), batch_size=config["batch_size"]
    )
    network = build_network(config["fc_layer_size"], config["dropout"])
    optimizer = optim.Adam(network.parameters(), lr=config["learning_rate"])
    for epoch in range(config["epochs"]):
        print("Epoch: %s" % epoch)
        avg_loss = train_epoch(network, loader, optimizer)
    return Model(weave.type_of(X), weave.type_of(y), network)
