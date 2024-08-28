import typing
from itertools import chain

import numpy as np
import pyarrow as pa
import pytest

import weave
from weave.legacy.weave import api, ops, storage, weave_internal
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.ops_arrow import ArrowWeaveList, arrow_as_array
from weave.legacy.weave.ops_domain.run_segment import RunSegment

N_NUMERIC_METRICS = 99  # number of numerical columns in the metrics table


def random_metrics(n: int = 10, starting_step: int = 0, delta_step: int = 1):
    """Create an array of metrics of length n starting from step starting_index."""
    if n <= 0:
        raise ValueError("n must be at least 1")
    if starting_step < 0:
        raise ValueError("starting index must be at least 0")
    if delta_step < 1:
        raise ValueError("delta_step must be an integer greater than or equal to 1.")

    data = {
        "step": np.arange(starting_step, starting_step + n * delta_step, delta_step),
        "string_col": np.random.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), n),
    }
    for j in range(N_NUMERIC_METRICS):
        data[f"metric{j}"] = np.random.random(n)
    return ArrowWeaveList(pa.table(data))


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

            return RunSegment(name, new_metrics, ref.uri, previous_segment_branch_index)
    return RunSegment(name, random_metrics(length, 0), None, 0)


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


def get_awl_col(awl: ArrowWeaveList, col_name: str):
    arr = arrow_as_array(awl._arrow_data)
    return arr.field(col_name)


@pytest.mark.parametrize("branch_frac", [0.0, 0.8, 1.0])
def test_experiment_branching(branch_frac, num_steps, num_runs):
    steps_per_run = num_steps // num_runs

    try:
        segment = create_experiment(num_steps, num_runs, branch_frac)
    except ValueError:
        assert branch_frac == 0
    else:
        storage.save(segment)
        experiment = api.use(segment.experiment())
        assert (
            len(experiment)
            == int(steps_per_run * branch_frac) * (num_runs - 1) + steps_per_run
        )

        assert (
            get_awl_col(experiment, "step").to_pylist()
            == list(range(int(steps_per_run * branch_frac) * (num_runs - 1)))
            + get_awl_col(segment.metrics, "step").to_pylist()
        )


@pytest.mark.parametrize("delta_step", [1, 2, 3])
def test_explicit_experiment_construction(delta_step):
    root_segment = RunSegment(
        "my-first-run", random_metrics(10, delta_step=delta_step), None, 0
    )
    ref1 = storage.save(root_segment)
    segment1 = RunSegment(
        "my-second-run",
        random_metrics(10, 5 * delta_step, delta_step=delta_step),
        ref1.uri,
        4,
    )
    ref2 = storage.save(segment1)
    segment2 = RunSegment(
        "my-third-run",
        random_metrics(5, 10 * delta_step, delta_step=delta_step),
        ref2.uri,
        4,
    )
    storage.save(segment2)
    experiment = api.use(segment2.experiment())

    assert get_awl_col(experiment, "step").to_pylist() == list(
        range(0, 15 * delta_step, delta_step)
    )
    assert (
        get_awl_col(experiment, "string_col").to_pylist()
        == get_awl_col(root_segment.metrics, "string_col").to_pylist()[:5]
        + get_awl_col(segment1.metrics, "string_col").to_pylist()[:5]
        + get_awl_col(segment2.metrics, "string_col").to_pylist()
    )

    assert get_awl_col(experiment, "run_name").to_pylist() == list(
        chain(
            *[[name] * 5 for name in ["my-first-run", "my-second-run", "my-third-run"]]
        )
    )


def test_invalid_explicit_experiment_construction():
    root_segment = RunSegment("my-first-run", random_metrics(10))
    ref1 = storage.save(root_segment)

    # this run has no metrics
    segment1 = RunSegment(
        "my-second-run",
        root_segment.metrics._limit(0),
        ref1.uri,
        4,
    )
    ref2 = storage.save(segment1)

    # this run tries to branch off a run with no metrics, which is not possible
    segment2 = RunSegment(
        "my-third-run",
        random_metrics(5, 10),
        ref2.uri,
        5,
    )
    storage.save(segment2)

    with pytest.raises(ValueError):
        api.use(segment2.experiment())


def test_vectorized_unnest_list_for_panelplot():
    metrics = random_metrics(10)
    root_segment = weave.save(RunSegment("my-first-run", metrics))

    def map_fn(row):
        return ops.dict_(
            **{
                "100": 100,
                "step": row["step"],
                "metric0": row["metric0"],
                "string_col": row["string_col"],
                "circle": "circle",
            }
        )

    fn_node = ops.define_fn(
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

    res = weave.use(root_segment.metrics.map(fn_node))
    mapped = res.to_pylist_raw()
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
    return ops.numbers_bins_equal([1, 2, 3, 4], 10)


def test_number_bin_fn_node_type(number_bin_fn_node):
    assert number_bin_fn_node.type == types.Function(
        input_types={"row": types.Number()},
        output_type=types.NumberBinType,
    )


def test_number_bin_generation(number_bin_fn_node):
    # extract the function from its containing node
    function = api.use(number_bin_fn_node)
    call_node = ops.call_fn(
        function, {"row": weave_internal.make_const_node(types.Number(), 2.5)}
    )
    result = api.use(call_node)

    assert np.isclose(result["start"], 2.4)
    assert np.isclose(result["stop"], 2.7)


def test_number_bin_assignment_in_bin_range(number_bin_fn_node):
    # create a graph representing bin assignment
    assigned_number_bin_node = ops.number_bin(in_=2.5, bin_fn=number_bin_fn_node)
    assigned_bin = api.use(assigned_number_bin_node)

    assert np.isclose(assigned_bin["start"], 2.4)
    assert np.isclose(assigned_bin["stop"], 2.7)


def test_number_bin_assignment_outside_bin_range(number_bin_fn_node):
    # now do one outside the original range
    assigned_number_bin_node = ops.number_bin(in_=7, bin_fn=number_bin_fn_node)
    assigned_bin = api.use(assigned_number_bin_node)

    assert np.isclose(assigned_bin["start"], 6.9)
    assert np.isclose(assigned_bin["stop"], 7.2)


def test_group_by_bins_arrow_vectorized():
    number_bin_fn_node = ops.numbers_bins_equal([0, 10], 2)
    segment = create_experiment(200, 5, 0.8)

    def groupby_func(row):
        step = row["step"]
        assigned_number_bin_node = ops.number_bin(in_=step, bin_fn=number_bin_fn_node)
        return ops.dict_(number_bin_col_name=assigned_number_bin_node)

    func_node = weave_internal.define_fn(
        {"row": api.type_of(segment.metrics).object_type}, groupby_func
    )
    groupby_node = weave_internal.const(segment.metrics).groupby(func_node)

    result = api.use(groupby_node)
    assert api.use(weave_internal.const(result).count()) == 9

    group_key_node = weave_internal.const(result)[4].groupkey()
    key = api.use(group_key_node)
    assert key == {"number_bin_col_name": {"start": 145.0, "stop": 150.0}}


# cache busting didn't work properly with this query before
def test_map_merge_cache_busting():
    root_segment = RunSegment("my-first-run", random_metrics(10))
    ref = storage.save(root_segment)

    def map_fn_1_body(row):
        const_dict = ops.dict_()
        merge_dict = ops.dict_(
            **{
                "100": 100,
                "step": row["step"],
                "metric0": row["metric0"],
                "string_col": row["string_col"],
                "circle": "circle",
            }
        )
        return const_dict.merge(merge_dict)

    fn_node = weave_internal.define_fn(
        {"row": root_segment.metrics.object_type}, map_fn_1_body
    )
    query = api.get(ref).metrics.map(fn_node)
    result1 = api.use(query)

    def map_fn_2_body(row):
        const_dict = ops.dict_()
        merge_dict = ops.dict_(
            **{
                "100": 100,
                "step": row["step"],
                "metric1": row["metric1"],
                "string_col": row["string_col"],
                "circle": "circle",
            }
        )
        return const_dict.merge(merge_dict)

    fn_node = weave_internal.define_fn(
        {"row": root_segment.metrics.object_type}, map_fn_2_body
    )
    query = api.get(ref).metrics.map(fn_node)
    result2 = api.use(query)

    assert result1._arrow_data != result2._arrow_data
    assert (
        result1._arrow_data.type.get_field_index("metric0") != -1
        and result2._arrow_data.type.get_field_index("metric0") == -1
    )
    assert (
        result1._arrow_data.type.get_field_index("metric1") == -1
        and result2._arrow_data.type.get_field_index("metric1") != -1
    )


@pytest.mark.skip()  # TODO(dg): enable
def test_map_experiment_profile_post_groupby_map():
    last_segment = create_experiment(500000, 20)
    experiment = last_segment.experiment()

    group_key_name = "steppybin(pybinsequal (list (2, 500) , 2) )"
    list_node = ops.list_.make_list(**{"0": 2, "1": 500})
    number_bin_fn_node = ops.numbers_bins_equal(list_node, 2)

    def groupby_fn(row):
        step = row.pick("step")
        assigned_number_bin_node = ops.number_bin(in_=step, bin_fn=number_bin_fn_node)
        return ops.dict_(**{group_key_name: assigned_number_bin_node})

    groupby_node = weave_internal.define_fn(
        {"row": experiment.type.object_type}, groupby_fn
    )
    groupby = experiment.groupby(groupby_node)

    def map_fn_1_body(row):
        row_key = ops.WeaveGroupResultInterface.key(row)
        merge_dict = ops.dict_(
            **{
                "100": 100,
                "step": row.pick("step"),
                "metric0": row.pick("metric0"),
                "string_col": row.pick("string_col"),
                "circle": "circle",
            }
        )
        return row_key.merge(merge_dict)

    map_fn_node = weave_internal.define_fn(
        {
            "row": ops.arrow.awl_group_by_result_object_type(
                experiment.type.object_type, groupby_node.type.output_type
            )
        },
        map_fn_1_body,
    )
    mapped = ops.list_.make_list(**{"0": ops.list_.unnest(groupby.map(map_fn_node))})

    import cProfile

    cProfile.runctx("use(mapped)", globals(), locals(), filename="map_profile.pstat")
