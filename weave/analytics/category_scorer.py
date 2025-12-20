"""Category-based scorers for trace classification."""

from typing import Any

import weave
from weave.flow.scorer import Scorer


def create_category_scorer(
    category_name: str,
    category_definition: str,
    classification_result: bool,
    confidence: float,
    reason: str,
) -> type[Scorer]:
    """Create a unique Weave Scorer class for a specific category with classification result.

    This creates a new class (not an instance) so each category has its own
    distinct scorer type in Weave's type system. The classification result
    is baked into the class as a class attribute.

    Args:
        category_name: The name of the category (no whitespace)
        category_definition: The definition of what traces belong to this category
        classification_result: Whether the trace belongs to this category (from LLM)
        confidence: Confidence score from the LLM classification
        reason: Reason for the classification decision

    Returns:
        A new Scorer class for this category with the result embedded

    Example:
        >>> AuthIssuesScorer = create_category_scorer(
        ...     "AuthenticationIssues",
        ...     "Traces where users cannot log in",
        ...     True,
        ...     0.85,
        ...     "Failed login detected"
        ... )
        >>> scorer = AuthIssuesScorer()
        >>> result = scorer.score(output={...})
        {'belongs_to_category': True, 'confidence': 0.85, 'reason': '...'}
    """

    class DynamicCategoryScorer(Scorer):
        """A scorer that determines if a trace belongs to a specific category.

        This scorer returns the classification result that was determined
        by the LLM during the classification phase.
        """

        # Store classification results as class attributes
        _classification_result: bool = classification_result
        _confidence: float = confidence
        _reason: str = reason

        @weave.op
        def score(
            self,
            *,
            output: Any,
            **kwargs: Any,
        ) -> dict:
            """Score whether a trace belongs to this category.

            Args:
                output: The trace output (required by Scorer interface)
                **kwargs: Additional arguments

            Returns:
                dict with belongs_to_category, confidence, and reason
            """
            return {
                "belongs_to_category": self._classification_result,
                "confidence": self._confidence,
                "reason": self._reason,
            }

    # Set the class name and module to make it unique
    DynamicCategoryScorer.__name__ = f"{category_name}Scorer"
    DynamicCategoryScorer.__qualname__ = f"{category_name}Scorer"
    DynamicCategoryScorer.__doc__ = f"""Scorer for category: {category_name}

Category Definition:
{category_definition}

Classification Result: {classification_result}
Confidence: {confidence}
Reason: {reason}

This scorer returns the classification determined by LLM analysis.
"""

    return DynamicCategoryScorer
