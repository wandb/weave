import torch
import weave


class TorchTensorType(weave.types.Type):
    instance_classes = torch.Tensor
    instance_class = torch.Tensor

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.pt", binary=True) as f:
            torch.save(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.pt", binary=True) as f:
            return torch.load(f)


class TorchModelType(weave.types.Type):
    instance_classes = torch.nn.Sequential
    instance_class = torch.nn.Sequential

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.pt", binary=True) as f:
            torch.save(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.pt", binary=True) as f:
            return torch.load(f)
