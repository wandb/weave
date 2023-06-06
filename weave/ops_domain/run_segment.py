import dataclasses
import typing
from typing import Optional, cast
from ..api import use, get, Node
from .. import weave_types as types
from .. import panels
from .. import context_state as _context
from ..ops_arrow import ArrowWeaveList, ArrowWeaveListType
import weave


_loading_builtins_token = _context.set_loading_built_ins()


@weave.type()
class RunSegment:
    run_name: str

    # this is an ArrowWeaveList containing a table with an arbitrary schema
    # except that one column should be called "step" and have cells of any
    # integer type
    metrics: typing.TypeVar("MetricRows")  # type: ignore

    prior_run_ref: typing.Optional[str] = dataclasses.field(
        default_factory=lambda: None
    )
    # index of the prior run's
    prior_run_branch_index: typing.Optional[int] = dataclasses.field(
        default_factory=lambda: None
    )

    @property
    def prior_run_branch_step(self) -> Optional[int]:
        if self.prior_run_branch_index is None:
            return None
        return self.metrics._index(self.prior_run_branch_index)["step"]

    def _experiment_body(self, limit: Optional[int] = None) -> ArrowWeaveList:

        if limit is None:
            limit = len(self.metrics)

        limited = self.metrics._limit(limit)._append_column(
            "run_name",
            [self.run_name] * limit,
        )

        if self.prior_run_ref is None:
            return limited

        # get the prior run
        prior_run: RunSegment = use(get(self.prior_run_ref))
        prior_experiment = prior_run._experiment_body(
            limit=self.prior_run_branch_index + 1
            if self.prior_run_branch_index is not None
            else 0
        )

        if len(prior_experiment) == 0:
            raise ValueError(
                f"Attempted to branch off of an empty run: run {prior_run} has no metrics."
            )

        return prior_experiment.concat(limited)

    @weave.op(render_info={"type": "function"}, hidden=True)
    def refine_experiment_type(self) -> types.Type:
        return ArrowWeaveListType(
            object_type=types.TypedDict(
                {**self.metrics.object_type.property_types, "run_name": types.String()}
            )
        )

    @weave.op(refine_output_type=refine_experiment_type)
    def experiment(self) -> typing.Any:
        return self._experiment_body()


@weave.op()
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


_context.clear_loading_built_ins(_loading_builtins_token)
