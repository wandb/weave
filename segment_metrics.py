from weave.ops_domain import RunSegment
from weave import storage, publish
import typing
import numpy as np
from weave.ops import to_arrow

# serializer = publish   # uses w&b artifacts intead of local artifacts
serializer = storage.save

N_METRICS = 100  # number of columns in the metrics table


def random_metrics(n=10, starting_index=0):
    """Create an array of metrics of length n starting from step starting_index."""
    return [
        {
            "step": starting_index + i + 1,
            **{f"metric{j + 1}": np.random.random() for j in range(N_METRICS)},
        }
        for i in range(n)
    ]


def create_branch(
    name: str,
    previous_segment: typing.Optional[RunSegment] = None,
    length=10,
    branch_frac=0.8,
) -> RunSegment:
    """Create a new segment and optionally attach it to a previous segment.

    Parameters
    ----------
    name: str
       The name of the segment.
    previous_segment: Optional[RunSegment], default None.
       The parent run segment. If this is a root run segment, use None.
    length: int, default = 10
       The number of history rows to generate for the segment.
    branch_frac: float between 0 and 1.
       Parameter describing where in the previous segment to set the branch point.
       A branch_frac of 0 sets the branch point at the previous segment's root,
       whereas a branch_frac of 1 sets the branch point at the end of the previous
       segment.

    Returns
    -------
    segment: RunSegment
        The new segment.
    """
    if previous_segment:
        previous_metrics = previous_segment.metrics
        starting_index = previous_metrics[0]["step"] + min(
            int(
                branch_frac
                * (previous_metrics[-1]["step"] - previous_metrics[0]["step"])
            ),
            len(previous_metrics) - 1,
        )

        ref = serializer(previous_segment)
        new_metrics = to_arrow(random_metrics(n=length, starting_index=starting_index))
        return RunSegment(name, ref.uri, starting_index, new_metrics)
    return RunSegment(name, None, 0, to_arrow(random_metrics(length, 0)))


def create_experiment(
    num_steps: int, num_runs: int, branch_frac: float = 0.8
) -> typing.Optional[RunSegment]:
    num_steps_per_run = num_steps // num_runs
    segment = None
    for i in range(num_runs):
        segment = create_branch(
            f"branch {i + 1}",
            segment,
            length=num_steps_per_run,
            branch_frac=branch_frac,
        )
    return segment
