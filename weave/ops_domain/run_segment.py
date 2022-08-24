import typing

from ..api import type, op, use, get, type_of, Node
from .. import panels
from .. import weave_types as types


@type()
class RunSegment:
    run_name: str
    prior_run_ref: typing.Optional[str]
    resumed_from_step: int
    metrics: typing.TypeVar("MetricRows")  # type: ignore

    @op(render_info={"type": "function"})
    def refine_experiment_type(self) -> types.Type:
        """Assuming a constant type over history rows for now."""
        segment = self
        metrics = segment.metrics
        resumed_from_step = self.resumed_from_step
        while len(metrics) == 0:
            if segment.prior_run_ref is None:
                # no history - return empty
                return types.List(object_type=types.Any())

            segment = use(get(segment.prior_run_ref))
            metrics = segment.metrics[:resumed_from_step]
            resumed_from_step = segment.resumed_from_step

        # get the first row and use it to infer the type
        example_row = metrics[0]
        name_type = types.TypedDict({"name": types.String()})
        return types.List(types.merge_types(type_of(example_row), name_type))

    def _experiment_body(self, until: typing.Optional[int] = None) -> typing.Any:
        prior_run_metrics: typing.Any = []
        if self.prior_run_ref is not None:
            # get the prior run
            prior_run: RunSegment = use(get(self.prior_run_ref))
            prior_run_metrics = prior_run._experiment_body(until=self.resumed_from_step)

        own_metrics: typing.Any = [
            {
                "step": d["step"],
                "name": self.run_name,
                **d,  # type: ignore
            }
            for d in self.metrics[:until]
        ]

        return prior_run_metrics + own_metrics

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
    run_segment = typing.cast(RunSegment, run_segment_node)

    return panels.Card(
        title=run_segment.run_name,
        subtitle="Weave Run Segment",
        content=[
            panels.CardTab(
                name="History",
                # TODO: this should just be run_segment.metrics
                content=run_segment.metrics,  # type: ignore
            ),
        ],
    )
