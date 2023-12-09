import typing

import weave
from ..artifact_wandb import WandbArtifactRef
from .dataset import Dataset


def publish_huggingface_dataset(
    hf_dataset_name: str,
    config_name: typing.Optional[str],
    split_name: str,
    sample_size: int,
    seed: int,
) -> WandbArtifactRef:
    import random
    from datasets import load_dataset

    if config_name is None:
        config_name = "default"

    dataset = load_dataset(hf_dataset_name, config_name)
    split = dataset[split_name]
    random.seed(seed)
    indexes = random.sample(range(len(split)), sample_size)
    sample = split.select(indexes)
    return weave.publish(
        Dataset(list(sample)),
        name=f"{hf_dataset_name}-{split_name}-{sample_size}-{seed}",
    )
