from __future__ import annotations

import dataclasses
import datetime
from concurrent.futures import Future
from typing import Any, Callable, TypedDict

from weave import ObjectRef
from weave.flow.scorer import Scorer, ApplyScorerResult
from weave.trace import urls
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.feedback import RefFeedbackQuery
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op
from weave.trace.ref_util import get_ref
from weave.trace.refs import OpRef, CallRef
from weave.trace.weave_client import elide_display_name, OpNameError, DEFAULT_CALLS_PAGE_SIZE, CallsIter, \
    _make_calls_iterator
from weave.trace_server.trace_server_interface import CallsFilter


@dataclasses.dataclass
class Call:
    """A Call represents a single operation executed as part of a trace.

    ``attributes`` are frozen once the call is created. Use
    :func:`weave.attributes` or ``create_call(..., attributes=...)`` to
    populate metadata beforehand. The ``summary`` dictionary may be
    modified while the call is running; its contents are deep-merged
    with computed summary values when :meth:`WeaveClient.finish_call`
    is invoked.
    """

    _op_name: str | Future[str]
    trace_id: str
    project_id: str
    parent_id: str | None
    inputs: dict[str, Any]
    id: str | None = None
    output: Any = None
    exception: str | None = None
    summary: dict[str, Any] | None = dataclasses.field(default_factory=dict)
    _display_name: str | Callable[[Call], str] | None = None
    attributes: dict[str, Any] | None = None
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    thread_id: str | None = None
    turn_id: str | None = None

    # These are the live children during logging
    _children: list[Call] = dataclasses.field(default_factory=list)
    _feedback: RefFeedbackQuery | None = None

    @property
    def display_name(self) -> str | Callable[[Call], str] | None:
        return self._display_name

    @display_name.setter
    def display_name(self, name: str | Callable[[Call], str] | None) -> None:
        if isinstance(name, str):
            name = elide_display_name(name)
        self._display_name = name

    @property
    def op_name(self) -> str:
        if isinstance(self._op_name, Future):
            self.__dict__["_op_name"] = self._op_name.result()

        if not isinstance(self._op_name, str):
            raise OpNameError(f"Call op_name is not a string: {self._op_name}")

        return self._op_name

    @property
    def func_name(self) -> str:
        """
        The decorated function's name that produced this call.

        This is different from `op_name` which is usually the ref of the op.
        """
        if self.op_name.startswith("weave:///"):
            ref = OpRef.parse_uri(self.op_name)
            return ref.name

        return self.op_name

    @property
    def feedback(self) -> RefFeedbackQuery:
        if not self.id:
            raise ValueError(
                "Can't get feedback for call without ID, was `weave.init` called?"
            )

        if self._feedback is None:
            try:
                entity, project = self.project_id.split("/")
            except ValueError:
                raise ValueError(f"Invalid project_id: {self.project_id}") from None
            weave_ref = CallRef(entity, project, self.id)
            self._feedback = RefFeedbackQuery(weave_ref.uri())
        return self._feedback

    @property
    def ui_url(self) -> str:
        if not self.id:
            raise ValueError(
                "Can't get URL for call without ID, was `weave.init` called?"
            )

        try:
            entity, project = self.project_id.split("/")
        except ValueError:
            raise ValueError(f"Invalid project_id: {self.project_id}") from None
        return urls.redirect_call(entity, project, self.id)

    @property
    def ref(self) -> CallRef:
        entity, project = self.project_id.split("/")
        if not self.id:
            raise ValueError(
                "Can't get ref for call without ID, was `weave.init` called?"
            )

        return CallRef(entity, project, self.id)

    # These are the children if we're using Call at read-time
    def children(self, *, page_size: int = DEFAULT_CALLS_PAGE_SIZE) -> CallsIter:
        """
        Get the children of the call.

        Args:
            page_size: Tune performance by changing the number of calls fetched at a time.

        Returns:
            An iterator of calls.
        """
        if not self.id:
            raise ValueError(
                "Can't get children of call without ID, was `weave.init` called?"
            )

        client = weave_client_context.require_weave_client()
        return _make_calls_iterator(
            client.server,
            self.project_id,
            CallsFilter(parent_ids=[self.id]),
            page_size=page_size,
        )

    def delete(self) -> bool:
        """Delete the call."""
        client = weave_client_context.require_weave_client()
        client.delete_call(call=self)
        return True

    def set_display_name(self, name: str | None) -> None:
        """
        Set the display name for the call.

        Args:
            name: The display name to set for the call.

        Example:

        ```python
        result, call = my_function.call("World")
        call.set_display_name("My Custom Display Name")
        ```
        """
        if name == "":
            raise ValueError(
                "Display name cannot be empty. To remove the display_name, set name=None or use remove_display_name."
            )
        if name == self.display_name:
            return
        client = weave_client_context.require_weave_client()
        client._set_call_display_name(call=self, display_name=name)
        self.display_name = name

    def remove_display_name(self) -> None:
        self.set_display_name(None)

    async def apply_scorer(
        self,
        scorer: Op | Scorer,
        additional_scorer_kwargs: dict[str, Any] | None = None,
    ) -> ApplyScorerResult:
        """
        `apply_scorer` is a method that applies a Scorer to a Call. This is useful
        for guarding application logic with a scorer and/or monitoring the quality
        of critical ops. Scorers are automatically logged to Weave as Feedback and
        can be used in queries & analysis.

        Args:
            scorer: The Scorer to apply.
            additional_scorer_kwargs: Additional kwargs to pass to the scorer. This is
                useful for passing in additional context that is not part of the call
                inputs.useful for passing in additional context that is not part of the call
                inputs.

        Returns:
            The result of the scorer application in the form of an `ApplyScorerResult`.

        ```python
        class ApplyScorerSuccess:
            result: Any
            score_call: Call
        ```

        Example usage:

        ```python
        my_scorer = ... # construct a scorer
        prediction, prediction_call = my_op.call(input_data)
        result, score_call = prediction.apply_scorer(my_scorer)
        ```
        """
        from weave.flow.scorer import Scorer, apply_scorer_async

        model_inputs = {k: v for k, v in self.inputs.items() if k != "self"}
        example = {**model_inputs, **(additional_scorer_kwargs or {})}
        output = self.output
        if isinstance(output, ObjectRef):
            output = output.get()
        apply_scorer_result = await apply_scorer_async(scorer, example, output)
        score_call = apply_scorer_result.score_call

        wc = weave_client_context.get_weave_client()
        if wc:
            scorer_ref = None
            if weave_isinstance(scorer, Scorer):
                # Very important: if the score is generated from a Scorer subclass,
                # then scorer_ref will be None, and we will use the op_name from
                # the score_call instead.
                scorer_ref = get_ref(scorer)
            wc._send_score_call(self, score_call, scorer_ref)
        return apply_scorer_result

    def to_dict(self) -> CallDict:
        if callable(display_name := self.display_name):
            display_name = "Callable Display Name (not called yet)"

        return CallDict(
            op_name=self.op_name,
            trace_id=self.trace_id,
            project_id=self.project_id,
            parent_id=self.parent_id,
            inputs=self.inputs,
            id=self.id,
            output=self.output,
            exception=self.exception,
            summary=self.summary,
            display_name=display_name,
            attributes=self.attributes,
            started_at=self.started_at,
            ended_at=self.ended_at,
            deleted_at=self.deleted_at,
            thread_id=self.thread_id,
            turn_id=self.turn_id,
        )


class NoOpCall(Call):
    def __init__(self) -> None:
        super().__init__(
            _op_name="", trace_id="", project_id="", parent_id=None, inputs={}
        )


class CallDict(TypedDict):
    op_name: str
    trace_id: str
    project_id: str
    parent_id: str | None
    inputs: dict[str, Any]
    id: str | None
    output: Any
    exception: str | None
    summary: dict[str, Any] | None
    display_name: str | None
    attributes: dict[str, Any] | None
    started_at: datetime.datetime | None
    ended_at: datetime.datetime | None
    deleted_at: datetime.datetime | None
    thread_id: str | None
    turn_id: str | None
