import pytest

from .ops_domain import RunSegment
from . import storage, type_of, use
from .weave_types import List
import typing
import time
import sys
import numpy as np
from .ops import to_arrow

import logging

logger = logging.getLogger("run_segment")
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
logger.addHandler(handler)

# set to logging.INFO for more verbose profiling
logger.setLevel(logging.ERROR)

# serializer = publish   # uses w&b artifacts intead of local artifacts
serializer = storage.save

N_NUMERIC_METRICS = 99  # number of numerical columns in the metrics table


def random_metrics(n=10, starting_index=0):
    """Create an array of metrics of length n starting from step starting_index."""
    logger.info(
        f"Creating a python list of {n} dicts with {N_NUMERIC_METRICS + 2} keys per dict."
    )
    start_time = time.time()
    raw = [
        {
            "step": starting_index + i + 1,
            "string_col": np.random.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")),
            **{f"metric{j + 1}": np.random.random() for j in range(N_NUMERIC_METRICS)},
        }
        for i in range(n)
    ]
    done_time = time.time()
    logger.info(f"Finished creating dict in {done_time - start_time:.2f} sec.")

    logger.info(f"Converting list-of-dict representation to arrow.")
    arrow_start_time = time.time()
    wb_type = List(type_of(raw[0]))
    arrow_form = to_arrow(raw, wb_type=wb_type)
    arrow_end_time = time.time()
    logger.info(
        f"Finished converting list-of-dict representation to arrow in {arrow_end_time - arrow_start_time:.2f} sec."
    )

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
    if previous_segment:
        previous_metrics = previous_segment.metrics
        starting_index = previous_metrics._index(0)["step"] + min(
            int(
                branch_frac
                * (
                    previous_metrics._index(len(previous_metrics) - 1)["step"]
                    - previous_metrics._index(0)["step"]
                )
            ),
            len(previous_metrics) - 1,
        )

        ref = serializer(previous_segment)
        new_metrics = random_metrics(n=length, starting_index=starting_index)
        return RunSegment(name, ref.uri, starting_index, new_metrics)
    return RunSegment(name, None, 0, random_metrics(length, 0))


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


@pytest.mark.parametrize("branch_frac", [0.0, 0.8, 1.0])
def test_experiment_branching(branch_frac):
    num_steps = 50000
    num_runs = 100
    steps_per_run = num_steps // num_runs
    segment = create_experiment(num_steps, num_runs, branch_frac)
    assert len(use(segment.experiment())) == steps_per_run * (
        (num_runs - 1) * branch_frac + 1
    )
