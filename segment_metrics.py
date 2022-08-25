from weave.ops_domain import RunSegment
from weave import storage, publish
import typing
import numpy as np

# serializer = publish   # uses w&b artifacts intead of local artifacts
serializer = storage.save


def random_metrics(n=10, starting_index=0):
    """Creates an array of metrics of length n starting from step starting_index."""
    return [
        {
            "step": starting_index + i + 1,
            "metricA": np.random.random() + np.exp(i / 2),
            "metricB": np.random.random() + np.exp(i / 4),
            "metricC": np.random.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")),
        }
        for i in range(n)
    ]


def create_branch(
    name: str,
    previous_segment: typing.Optional[RunSegment],
    length=10,
    branch_frac=0.8,
) -> RunSegment:
    if previous_segment:
        previous_metrics = previous_segment.metrics
        starting_index = previous_metrics[0]["step"] + min(
            int(
                branch_frac * previous_metrics[-1]["step"] - previous_metrics[0]["step"]
            ),
            len(previous_metrics) - 1,
        )

        ref = serializer(previous_segment)
        new_metrics = random_metrics(n=length, starting_index=starting_index)
        return RunSegment(name, ref.uri, starting_index, new_metrics)
    return RunSegment(name, None, 0, random_metrics(length, 0))
