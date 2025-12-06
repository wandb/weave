from __future__ import annotations

from typing import TYPE_CHECKING, Any

from weave.flow.scorer import Scorer
from weave.prompt.prompt import MessagesPrompt
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.objectify import maybe_objectify, register_object
from weave.trace.op import op
from weave.trace.vals import make_trace_obj
from weave.trace.weave_client import ObjectRef, from_json
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
    Message,
)

if TYPE_CHECKING:
    from weave.trace_server.trace_server_interface import TraceServerInterface


def _load_prompt_from_ref(
    prompt_ref_uri: str, server: TraceServerInterface
) -> MessagesPrompt:
    """Load a MessagesPrompt from a ref URI using direct server access.

    Args:
        prompt_ref_uri: The weave:/// URI pointing to the prompt object.
        server: The trace server to use for loading.

    Returns:
        The resolved MessagesPrompt object.
    """
    try:
        prompt_ref = ObjectRef.parse_uri(prompt_ref_uri)
    except ValueError as exc:
        raise ValueError(
            f"Invalid scoring_prompt_ref '{prompt_ref_uri}'. Expected a weave:/// URI."
        ) from exc

    prompt_project_id = f"{prompt_ref.entity}/{prompt_ref.project}"

    prompt_obj = server.obj_read(
        tsi.ObjReadReq(
            project_id=prompt_project_id,
            object_id=prompt_ref.name,
            digest=prompt_ref.digest,
        )
    ).obj

    prompt_val = from_json(prompt_obj.val, prompt_project_id, server)
    prompt = maybe_objectify(
        make_trace_obj(
            prompt_val,
            None,
            server,
            None,
        )
    )

    if not isinstance(prompt, MessagesPrompt):
        raise TypeError(
            f"Prompt ref '{prompt_ref_uri}' did not resolve to a MessagesPrompt (got {type(prompt)!r})."
        )

    return prompt


@register_object
class LLMAsAJudgeScorer(Scorer):
    """LLM as a judge scorer that can use either a prompt string or a prompt reference.

    Attributes:
        model: The LLM model to use for scoring
        scoring_prompt: A prompt string template with {variable} placeholders (optional if scoring_prompt_ref is provided)
        scoring_prompt_ref: A reference to a MessagesPrompt object, either as a URI string
            or the resolved MessagesPrompt object (optional, takes precedence over scoring_prompt)
    """

    model: LLMStructuredCompletionModel
    scoring_prompt: str | None = None
    # Accept both string (ref URI) and MessagesPrompt (resolved ref from weave.get())
    scoring_prompt_ref: str | MessagesPrompt | None = None

    def build_scoring_messages(
        self,
        template_vars: dict[str, Any],
        server: TraceServerInterface | None = None,
    ) -> list[Message]:
        """Build scoring messages from prompt or prompt_ref.

        Args:
            template_vars: Variables to substitute in the prompt template.
            server: Optional trace server for direct ref resolution. This is used by
                the scoring worker which processes scoring requests for many different
                projects/entities. Re-initializing a weave client for each project would
                be expensive, so the worker passes the server directly to bypass
                client-based resolution.

        Returns:
            List of Message objects ready for the model.
        """
        if self.scoring_prompt_ref is not None:
            # Handle both string refs and already-resolved MessagesPrompt objects
            if isinstance(self.scoring_prompt_ref, MessagesPrompt):
                prompt_obj = self.scoring_prompt_ref
            elif server is not None:
                # Direct server access - used by the scoring worker to avoid
                # reinitializing a client for each project being scored
                prompt_obj = _load_prompt_from_ref(self.scoring_prompt_ref, server)
            else:
                # Client-based resolution for normal SDK usage
                client = get_weave_client()
                if client is None:
                    raise ValueError(
                        "Weave client not initialized. Call weave.init() first."
                    )
                prompt_obj = client.get(self.scoring_prompt_ref)

            if not isinstance(prompt_obj, MessagesPrompt):
                raise TypeError(
                    f"Prompt object at {self.scoring_prompt_ref} is not a MessagesPrompt"
                )
            # Convert dicts to Message objects for type consistency
            formatted_messages = prompt_obj.format(**template_vars)
            return [Message(**msg) for msg in formatted_messages]

        if self.scoring_prompt is None:
            raise ValueError(
                "Either scoring_prompt or scoring_prompt_ref must be provided to LLMAsAJudgeScorer"
            )

        formatted = self.scoring_prompt.format(**template_vars)
        return [Message(role="user", content=formatted)]

    @op
    def score(self, *, output: str, **kwargs: Any) -> Any:
        """Score the output using the scoring_prompt.

        Args:
            output: The model output to score
            **kwargs: Additional template variables for the prompt

        Returns:
            The model's prediction/score
        """
        messages = self.build_scoring_messages({"output": output, **kwargs})
        return self.model.predict(messages)
