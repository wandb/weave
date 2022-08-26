import typing
from typing import Optional, cast
from ..api import type, op, use, get, type_of, Node
from .. import weave_types as types
from .. import panels
from ..ops_primitives.arrow import ArrowWeaveList


@type()
class RunSegment:
    run_name: str
    prior_run_ref: Optional[str]
    resumed_from_step: int
    metrics: typing.TypeVar("MetricRows")  # type: ignore

    def _experiment_body(self, until: Optional[int] = None) -> ArrowWeaveList:
        my_first_step = self.metrics._index(0)["step"]
        limit = until - my_first_step + 1 if until else len(self.metrics)
        limited = self.metrics._limit(limit)

        if self.prior_run_ref is None:
            return limited

        # get the prior run
        prior_run: RunSegment = use(get(self.prior_run_ref))
        prior_run_metrics = prior_run._experiment_body(until=self.resumed_from_step)
        return limited.concatenate(prior_run_metrics)

    @op(render_info={"type": "function"})
    def refine_experiment_type(self) -> types.Type:
        """Assuming a constant type over history rows for now."""

        segment = self
        metrics = segment.metrics

        # get the first row and use it to infer the type
        example_row = metrics._index(0)
        # name_type = types.TypedDict({"name": types.String()})
        return types.List(type_of(example_row))

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
