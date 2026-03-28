"""CodeScorer - a scorer whose score() method runs in a sandboxed container."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from weave.flow.scorer import Scorer
from weave.trace.objectify import register_object
from weave.trace.op import op


@register_object
class CodeScorer(Scorer):
    """Base class for scorers whose score() method runs in a sandboxed container.

    Subclass this and implement score() just like any other Scorer. When used in
    an online monitor, the scoring worker executes score() in an isolated container
    instead of in-process, using the declared environment (requirements or
    docker_image).

    For offline evaluation via weave.Evaluation, score() runs locally in the
    caller's process as normal — no sandbox is involved.

    At least one of `requirements` or `docker_image` must be set.

    Example::

        class ExactMatchScorer(CodeScorer):
            requirements: list[str] = ["rapidfuzz>=3.0"]

            @weave.op
            def score(self, *, output: str, reference: str) -> dict:
                from rapidfuzz import fuzz
                return {"similarity": fuzz.ratio(output, reference) / 100}

        scorer = ExactMatchScorer(name="exact-match")
        weave.publish(scorer)
    """

    requirements: list[str] | None = Field(
        default=None,
        description="Pip packages to install in the sandbox (e.g. ['nltk>=3.8', 'numpy']).",
    )
    docker_image: str | None = Field(
        default=None,
        description=(
            "Docker image to use as the sandbox base environment. "
            "Mutually exclusive with requirements."
        ),
    )
    secrets: list[str] | dict[str, str] | None = Field(
        default=None,
        description=(
            "Secrets to inject as environment variables into the sandbox. "
            "A list of secret names injects them under their own names. "
            'Use "*" in a list to inject all entity-level secrets. '
            "A dict maps secret names to the env var name they are injected as."
        ),
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.requirements is None and self.docker_image is None:
            raise ValueError(
                "CodeScorer requires at least one of `requirements` or `docker_image`."
            )
        if self.requirements is not None and self.docker_image is not None:
            raise ValueError(
                "CodeScorer accepts only one of `requirements` or `docker_image`, not both."
            )

    @op
    def score(self, *, output: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement score()."
        )
