import pytest
from itertools import chain

from ..ops_domain import RunSegment
from .. import storage, type_of, use
from ..weave_types import List
import typing
import numpy as np
from ..ops import to_arrow

N_NUMERIC_METRICS = 99  # number of numerical columns in the metrics table


def random_metrics(n: int = 10, starting_step: int = 0, delta_step: int = 1):
    """Create an array of metrics of length n starting from step starting_index."""
    if n <= 0:
        raise ValueError("n must be at least 1")
    if starting_step < 0:
        raise ValueError("starting index must be at least 0")
    if delta_step < 1:
        raise ValueError("delta_step must be an integer greater than or equal to 1.")
    raw = [
        {
            "step": starting_step + i * delta_step,
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
    previous_segment_branch_frac=0.8,
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
    previous_segment_branch_frac: float satisfying 0 < branch_frac <= 1.
       Parameter describing where in the previous segment to set the branch point.
       A previous_segment_branch_frac of 0 sets the branch point at the previous
       segment's root, whereas a previous_segment_branch_frac of 1 sets the branch
       point at the end of the previous segment. A previous_segment_branch_frac of
       0.5 would include half of the previous segment's metric rows.

    Returns
    -------
    segment: RunSegment
        The new segment.
    """
    if not (0 < previous_segment_branch_frac <= 1):
        raise ValueError("branch_frac must satisfy 0 < branch_frac <= 1")

    if length <= 0:
        raise ValueError("Length must be greater than 0.")

    if previous_segment:
        previous_metrics = previous_segment.metrics
        n_previous_metrics = len(previous_metrics)
        if n_previous_metrics > 0:
            previous_segment_branch_index = (
                int(previous_segment_branch_frac * n_previous_metrics) - 1
            )

            # this run segment has a different root than the previous one
            if previous_segment_branch_index < 0:
                raise ValueError(
                    f"Invalid branch point on RunSegment: previous_segment_branch_index "
                    f"{previous_segment_branch_index} must be between 0 and {len(previous_metrics) - 1}"
                )

            previous_segment_branch_step = (
                previous_metrics._index(0)["step"] + previous_segment_branch_index
            )

            ref = storage.save(previous_segment)
            new_metrics = random_metrics(
                n=length, starting_step=previous_segment_branch_step + 1
            )

            return RunSegment(name, ref.uri, previous_segment_branch_index, new_metrics)
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
            previous_segment_branch_frac=branch_frac,
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

    try:
        segment = create_experiment(num_steps, num_runs, branch_frac)
    except ValueError:
        assert branch_frac == 0
    else:
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


@pytest.mark.parametrize("delta_step", [1, 2, 3])
def test_explicit_experiment_construction(delta_step):
    root_segment = RunSegment(
        "my-first-run", None, 0, random_metrics(10, delta_step=delta_step)
    )
    ref1 = storage.save(root_segment)
    segment1 = RunSegment(
        "my-second-run",
        ref1.uri,
        4,
        random_metrics(10, 5 * delta_step, delta_step=delta_step),
    )
    ref2 = storage.save(segment1)
    segment2 = RunSegment(
        "my-third-run",
        ref2.uri,
        4,
        random_metrics(5, 10 * delta_step, delta_step=delta_step),
    )
    experiment = use(segment2.experiment())

    assert experiment._get_col("step").to_pylist() == list(
        range(0, 15 * delta_step, delta_step)
    )
    assert (
        experiment._get_col("string_col").to_pylist()
        == root_segment.metrics._get_col("string_col").to_pylist()[:5]
        + segment1.metrics._get_col("string_col").to_pylist()[:5]
        + segment2.metrics._get_col("string_col").to_pylist()
    )

    assert experiment._get_col("run_name").to_pylist() == list(
        chain(
            *[[name] * 5 for name in ["my-first-run", "my-second-run", "my-third-run"]]
        )
    )


def test_invalid_explicit_experiment_construction():
    root_segment = RunSegment("my-first-run", None, 0, random_metrics(10))
    ref1 = storage.save(root_segment)

    # this run has no metrics
    segment1 = RunSegment(
        "my-second-run",
        ref1.uri,
        4,
        root_segment.metrics._limit(0),
    )
    ref2 = storage.save(segment1)

    # this run tries to branch off a run with no metrics, which is not possible
    segment2 = RunSegment(
        "my-third-run",
        ref2.uri,
        5,
        random_metrics(5, 10),
    )

    with pytest.raises(ValueError):
        use(segment2.experiment())
