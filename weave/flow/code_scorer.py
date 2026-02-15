"""CodeScorer - a scorer that executes user code in a sandboxed container."""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from weave.flow.scorer import Scorer
from weave.trace.objectify import register_object


@register_object
class CodeScorer(Scorer):
    """A scorer that runs a user-published Op in a gVisor-sandboxed Docker container.

    The Op is resolved from its ref, executed in an isolated container with the
    configured environment, and results are logged back as feedback.

    At least one of docker_image or requirements must be set.
    """

    op_ref: str = Field(
        description="URI reference to the published Weave Op to execute"
    )
    docker_image: str | None = Field(
        default=None,
        description="Docker image to use as the sandbox environment",
    )
    requirements: list[str] | None = Field(
        default=None,
        description="Pip requirements to install in the sandbox",
    )
    use_pip: bool = Field(
        default=False,
        description="Use pip instead of uv for dependency resolution",
    )
    secrets: list[str] | dict[str, str] | None = Field(
        default=None,
        description=(
            "Secrets to inject as environment variables in the sandbox. "
            "Pass a list of secret names (injected as-is), "
            'the string "*" in a list to inject all entity secrets, '
            "or a dict mapping secret names to env var names."
        ),
    )

    @model_validator(mode="after")
    def validate_environment(self) -> CodeScorer:
        if self.docker_image is None and self.requirements is None:
            raise ValueError(
                "CodeScorer requires at least one of docker_image or requirements"
            )
        if self.docker_image is not None and self.requirements is not None:
            raise ValueError(
                "CodeScorer accepts only one of docker_image or requirements, not both"
            )
        return self

    def score(self, *, output: Any, **kwargs: Any) -> Any:
        """Not executed directly - the code execution worker handles this."""
        raise NotImplementedError(
            "CodeScorer.score() should not be called directly. "
            "It is executed by the code execution worker in a sandbox."
        )
