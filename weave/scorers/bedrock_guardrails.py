from typing import Any, Literal

from pydantic import Field, PrivateAttr

import weave
from weave.flow.scorer import WeaveScorerResult
from weave.integrations.bedrock import patch_client


class BedrockGuardrailScorer(weave.Scorer):
    """
    The `BedrockGuardrailScorer` class is a guardrail that leverages AWS Bedrock's
    guardrail functionality to detect and filter content based on configured policies.

    Attributes:
        guardrail_id (str): The identifier of the guardrail to use.
        guardrail_version (str): The version of the guardrail to use.
        source (str): The source of the content to evaluate, either 'INPUT' or 'OUTPUT'.

    Note:
        This scorer requires AWS Bedrock client to be properly configured with
        appropriate permissions to access the guardrail API.
    """

    guardrail_id: str = Field(description="The identifier of the guardrail to use.")
    guardrail_version: str = Field(
        default="DRAFT", description="The version of the guardrail to use."
    )
    source: Literal["INPUT", "OUTPUT"] = Field(
        default="OUTPUT",
        description="The source of the content to evaluate, either 'INPUT' or 'OUTPUT'.",
    )
    bedrock_runtime_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional keyword arguments to pass to the Bedrock runtime client.",
    )

    # Private attributes
    _bedrock_runtime: Any = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        """Initialize the Bedrock runtime client."""
        try:
            import boto3

            self._bedrock_runtime = boto3.client(
                "bedrock-runtime", **self.bedrock_runtime_kwargs
            )
            patch_client(self._bedrock_runtime)
        except ImportError:
            raise ImportError(
                "boto3 is not installed. Please install it with 'pip install boto3' "
                "to use the BedrockGuardrailScorer."
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Bedrock runtime client: {e}")

    def format_content(self, output: str) -> dict[str, Any]:
        """Format the content for the guardrail API."""
        return {"source": self.source, "content": [{"text": {"text": output}}]}

    @weave.op
    def score(self, *, output: str, **kwargs: Any) -> WeaveScorerResult:
        if self._bedrock_runtime is None:
            raise ValueError("Bedrock runtime client is not initialized")

        try:
            # Format the content for the guardrail API
            content = self.format_content(output)

            # Call the ApplyGuardrail API
            response = self._bedrock_runtime.apply_guardrail(
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion=self.guardrail_version,
                source=self.source,
                content=content["content"],
            )

            # Check if the guardrail intervened
            passed = response.get("action") != "GUARDRAIL_INTERVENED"

            assessments = response.get("assessments", [{}])[0]

            # Get the modified output if available
            modified_output = None
            if response.get("outputs") and len(response["outputs"]) > 0:
                modified_output = response["outputs"][0].get("text")

            return WeaveScorerResult(
                passed=passed,
                metadata={
                    "modified_output": modified_output,
                    "usage": response.get("usage", {}),
                    "assessments": assessments,
                },
            )
        except Exception as e:
            return WeaveScorerResult(
                passed=False,
                metadata={
                    "error": f"Error applying Bedrock guardrail: {str(e)}",
                    "reason": f"Error applying Bedrock guardrail: {str(e)}",
                },
            )
