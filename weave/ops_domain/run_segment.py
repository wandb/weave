import typing
import bisect
from typing import Optional, cast, Sequence
from ..api import type, op, use, get, type_of, Node
from .. import weave_types as types
from .. import panels
from ..ops_primitives.arrow import ArrowWeaveList


@type()
class RunSegment:
    run_name: str
    prior_run_ref: Optional[str]
    previous_run_branch_step: Optional[int]
    metrics: typing.TypeVar("MetricRows")  # type: ignore

    def _experiment_body(self, slice_end: Optional[int] = None) -> ArrowWeaveList:
        class ListWithCustomAccessor(Sequence):
            def __init__(self, data):
                self.data = data

            def __getitem__(self, i):
                return self.data._index(i)["step"]

            def __len__(self):
                return len(self.data)

        # log(n) solution to find the number of records to insert assuming step
        # is monotonically increasing but not uniformly spaced
        limit = (
            bisect.bisect_left(
                ListWithCustomAccessor(self.metrics),
                slice_end,
            )
            if slice_end is not None and len(self.metrics) != 0
            else len(self.metrics)
        )

        limited = self.metrics._limit(limit)._append_column(
            "run_name", [self.run_name] * limit, weave_type=types.String()
        )

        if self.prior_run_ref is None:
            return limited

        # get the prior run
        prior_run: RunSegment = use(get(self.prior_run_ref))
        prior_run_metrics = prior_run._experiment_body(
            slice_end=self.previous_run_branch_step
            if self.previous_run_branch_step is not None
            else self.previous_run_branch_step
        )
        if len(prior_run_metrics) > 0:
            return limited.concatenate(prior_run_metrics)
        return limited

    @op(render_info={"type": "function"})
    def refine_experiment_type(self) -> types.Type:
        """Assuming a constant type over history rows for now."""
        # get the first row and use it to infer the type
        example_row = self.metrics._index(0)
        name_type = types.TypedDict({"run_name": types.String()})
        return types.List(types.merge_types(type_of(example_row), name_type))

    @op(refine_output_type=refine_experiment_type)
    def experiment(self) -> typing.Any:
        return self._experiment_body()


@op()
def run_segment_render(
    run_segment_node: Node[RunSegment],
) -> panels.Card:

    # All methods callable on X are callable on weave.Node[X], but
    # the types arent' setup properly, so cast to tell the type-checker
    # TODO: Fix!
    run_segment = cast(RunSegment, run_segment_node)

    return panels.Card(
        title=run_segment.run_name,
        subtitle="Weave Run Segment",
        content=[
            panels.CardTab(
                name="History",
                content=run_segment.metrics,
            ),
        ],
    )
