import pytest

from .ops_domain import RunSegment
from . import storage, type_of, use
from .weave_types import List
import typing
import numpy as np
from .ops import to_arrow

# serializer = publish   # uses w&b artifacts intead of local artifacts
serializer = storage.save

N_NUMERIC_METRICS = 99  # number of numerical columns in the metrics table


def random_metrics(n: int = 10, starting_step: int = 0):
    """Create an array of metrics of length n starting from step starting_index."""
    if n <= 0:
        raise ValueError("n must be at least 1")
    if starting_step < 0:
        raise ValueError("starting index must be at least 0")
    raw = [
        {
            "step": starting_step + i,
            "string_col": np.random.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")),
            **{f"metric{j}": np.random.random() for j in range(N_NUMERIC_METRICS)},
        }
        for i in range(n)
    ]

    wb_type = List(type_of(raw[0]))
    arrow_form = to_arrow(raw, wb_type=wb_type)
    return arrow_form


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
    if not (0 <= branch_frac <= 1):
        raise ValueError("branch_frac must be between 0 and 1")

    if previous_segment:
        previous_metrics = previous_segment.metrics
        n_previous_metrics = len(previous_metrics)
        if n_previous_metrics > 0:
            previous_run_branch_step = previous_metrics._index(0)["step"] + int(
                branch_frac * n_previous_metrics
            )
            ref = serializer(previous_segment)
            new_metrics = random_metrics(
                n=length, starting_step=previous_run_branch_step + 1
            )
            return RunSegment(name, ref.uri, previous_run_branch_step, new_metrics)
    return RunSegment(name, None, 0, random_metrics(length, 0))


def create_experiment(
    num_steps: int, num_runs: int, branch_frac: float = 0.8
) -> typing.Optional[RunSegment]:
    num_steps_per_run = num_steps // num_runs
    segment = None
    for i in range(num_runs):
        segment = create_branch(
            f"branch {i}",
            segment,
            length=num_steps_per_run,
            branch_frac=branch_frac,
        )
    return segment


@pytest.fixture()
def num_steps():
    return 100


@pytest.fixture()
def num_runs():
    return 20


@pytest.mark.parametrize("branch_frac", [0.0, 0.8, 1.0])
def test_experiment_branching(branch_frac, num_steps, num_runs):
    steps_per_run = num_steps // num_runs
    segment = create_experiment(num_steps, num_runs, branch_frac)
    experiment = use(segment.experiment())
    assert (
        len(experiment)
        == int(steps_per_run * branch_frac) * (num_runs - 1) + steps_per_run
    )

    assert (
        experiment._get_col("step").to_pylist()
        == list(range(int(steps_per_run * branch_frac) * (num_runs - 1)))
        + segment.metrics._get_col("step").to_pylist()
    )
