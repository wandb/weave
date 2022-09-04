import pytest
from itertools import chain

from .ops_domain import RunSegment
from . import storage, type_of, use
from .weave_types import List
from . import weave_types as types
import typing
import numpy as np
from .ops import to_arrow, dict_, numbers_bins_equal, NumberBinType, number_bin

from .weave_internal import define_fn, call_fn, make_const_node

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
            previous_run_branch_step = (
                previous_metrics._index(0)["step"]
                + int(branch_frac * n_previous_metrics)
                - 1
            )
            ref = storage.save(previous_segment)
            new_metrics = random_metrics(
                n=length, starting_step=previous_run_branch_step + 1
            )

            # this run segment has a different root than the previous one
            if previous_run_branch_step < 0:
                previous_run_branch_step = None

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

    try:
        experiment = use(segment.experiment())
    except ValueError:
        assert branch_frac == 0
    else:
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
        4 * delta_step,
        random_metrics(10, 5 * delta_step, delta_step=delta_step),
    )
    ref2 = storage.save(segment1)
    segment2 = RunSegment(
        "my-third-run",
        ref2.uri,
        9 * delta_step,
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


def test_vectorized_unnest_list_for_panelplot():
    metrics = random_metrics(10)
    root_segment = RunSegment("my-first-run", None, 0, metrics)
    storage.save(root_segment)

    def map_fn(row):
        return dict_(
            **{
                "100": 100,
                "step": row["step"],
                "metric0": row["metric0"],
                "string_col": row["string_col"],
                "circle": "circle",
            }
        )

    fn_node = define_fn(
        {
            "row": types.TypedDict(
                {
                    "100": types.Int(),
                    "step": types.Int(),
                    "metric0": types.Float(),
                    "string_col": types.String(),
                    "circle": types.String(),
                }
            )
        },
        map_fn,
    )

    res = root_segment.metrics.map(fn_node)
    mapped = use(res).to_pylist()
    metrics_arr = metrics._arrow_data.to_pylist()
    assert mapped == [
        {
            "100": 100,
            "circle": "circle",
            "string_col": metrics_arr[i]["string_col"],
            "metric0": metrics_arr[i]["metric0"],
            "step": i,
        }
        for i in range(len(metrics))
    ]


@pytest.fixture()
def number_bin_fn_node():
    return numbers_bins_equal([1, 2, 3, 4], 10)


def test_number_bin_fn_node_type(number_bin_fn_node):
    assert number_bin_fn_node.type == types.Function(
        input_types={"row": types.Number()},
        output_type=NumberBinType,
    )


def test_number_bin_generation(number_bin_fn_node):
    # extract the function from its containing node
    function = use(number_bin_fn_node)
    call_node = call_fn(function, {"row": make_const_node(types.Number(), 2.5)})
    result = use(call_node)

    assert np.isclose(result["start"], 2.4)
    assert np.isclose(result["stop"], 2.7)


def test_number_bin_assignment_in_bin_range(number_bin_fn_node):
    # create a graph representing bin assignment
    assigned_number_bin_node = number_bin(in_=2.5, bin_fn=number_bin_fn_node)
    assigned_bin = use(assigned_number_bin_node)

    assert np.isclose(assigned_bin["start"], 2.4)
    assert np.isclose(assigned_bin["stop"], 2.7)


def test_number_bin_assignment_outside_bin_range(number_bin_fn_node):
    # now do one outside the original range
    assigned_number_bin_node = number_bin(in_=7, bin_fn=number_bin_fn_node)
    assigned_bin = use(assigned_number_bin_node)

    assert np.isclose(assigned_bin["start"], 6.9)
    assert np.isclose(assigned_bin["stop"], 7.2)


def test_group_by_bins_arrow_vectorized():
    number_bin_fn_node = numbers_bins_equal([0, 10], 2)
    segment = create_experiment(200, 5, 0.8)

    def groupby_func(row):
        step = row["step"]
        assigned_number_bin_node = number_bin(in_=step, bin_fn=number_bin_fn_node)
        return dict_(number_bin_col_name=assigned_number_bin_node)

    func_node = define_fn({"row": type_of(segment.metrics).object_type}, groupby_func)
    groupby_node = segment.metrics.groupby(func_node)

    result = use(groupby_node)
    assert use(result.count()) == 9

    group_key_node = result[4].key()
    key = use(group_key_node)
    assert key == {"number_bin_col_name": {"start": 130.0, "stop": 135.0}}
