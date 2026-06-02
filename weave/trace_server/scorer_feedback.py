from __future__ import annotations

import logging
import re
from typing import Annotated, Any, TypeAlias

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("weave.trace_server.scorer_feedback")

ScorerFeedbackFieldValue: TypeAlias = list[str] | dict[str, Any]
ScorerFeedbackFields: TypeAlias = dict[str, ScorerFeedbackFieldValue]

_MAX_TAGS_PER_ROW = 10
_MAX_TAG_LENGTH = 36
_MAX_REASON_LENGTH = 256

# Currently we allow scorers to emit a single numeric rating, which always uses this key.
# If we choose to allow multiple ratings in the future we can remove this constant.
_SCORER_RATING_MAP_KEY = "_rating_"

# A scorer LLM might give a reason for *not* tagging, which we assign to this sentinel.
_SCORER_EMPTY_TAG_KEY = "_empty_"

# Regex for chars allowed in tags and reasons. Whitespace will be removed from tags separately.
_SCORER_METADATA_CHARS_RE = re.compile(r"[^0-9a-zA-Z \.,;\-&!@#$%?]")

_TagType = Annotated[str, Field(max_length=_MAX_TAG_LENGTH)]
_RatingType = Annotated[float, Field(ge=0.0, le=1.0)]


class ScorerLlmOutputSchema(BaseModel):
    """Schema for a single scorer tag or rating. Extra keys are ignored."""

    value: _TagType | _RatingType
    reason: str | None = Field(default=None, max_length=_MAX_REASON_LENGTH)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("value", "confidence", mode="before")
    @classmethod
    def reject_bool_as_number(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise ValueError("boolean values are not valid scorer numbers")  # noqa: TRY004
        return v


class ScorerLlmOutputGroup(BaseModel):
    """Schema for a list of scorer tag or rating outputs."""

    scores: list[ScorerLlmOutputSchema]

    @staticmethod
    def from_raw_output(obj: Any) -> ScorerLlmOutputGroup:
        """Parse and validate scorer output in any of 3 formats:
        - A single score payload:  `{"value": "ok"}`
        - A list of scores:        `[{"value": "ok"}, {"value": 0.5}]`
        - A nested list of scores: `{"scores": [{"value": 0.9}]}`
        """
        if isinstance(obj, list):
            return ScorerLlmOutputGroup.model_validate({"scores": obj})
        if not isinstance(obj, dict):
            raise TypeError(f"Invalid scorer output type: {type(obj).__name__}")
        if isinstance(obj.get("scores"), list):
            return ScorerLlmOutputGroup.model_validate(obj)
        return ScorerLlmOutputGroup(scores=[ScorerLlmOutputSchema.model_validate(obj)])

    @staticmethod
    def from_agent_scorer_output(obj: Any) -> ScorerLlmOutputGroup:
        """Backward-compatible alias for the agent scoring worker."""
        return ScorerLlmOutputGroup.from_raw_output(obj)


class ScorerColumns(BaseModel):
    """Represents a row of `feedback.score_*` columns in the DB.
    Includes helper methods for normalizing raw scorer output.
    """

    tags: list[str] = Field(default_factory=list)
    ratings: dict[str, float] = Field(default_factory=dict)
    tag_reasons: dict[str, str] = Field(default_factory=dict)
    tag_confidences: dict[str, float] = Field(default_factory=dict)
    rating_reasons: dict[str, str] = Field(default_factory=dict)
    rating_confidences: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def from_raw_output(cls, output: Any) -> ScorerColumns:
        """Return normalized `feedback.score_*` columns from raw scorer output."""
        group = ScorerLlmOutputGroup.from_raw_output(output)
        return cls.from_scorer_llm_output_group(group)

    @classmethod
    def from_scorer_llm_output_group(cls, group: ScorerLlmOutputGroup) -> ScorerColumns:
        """Return normalized `feedback.score_*` columns from LLM output."""
        cols = ScorerColumns()

        for output in group.scores:
            if isinstance(output.value, str):
                cols._add_tag(output.value, output.reason, output.confidence)
            elif isinstance(output.value, float):
                cols._add_rating(output.value, output.reason, output.confidence)
            else:
                raise TypeError(
                    f'Invalid output value: {type(output.value)} "{output.value}"'
                )
        return cols

    def to_feedback_fields(self) -> ScorerFeedbackFields:
        """Return the column names/values expected by FeedbackCreateReq and feedback rows."""
        return {
            "scorer_tags": self.tags,
            "scorer_tag_reasons": self.tag_reasons,
            "scorer_tag_confidences": self.tag_confidences,
            "scorer_ratings": self.ratings,
            "scorer_rating_reasons": self.rating_reasons,
            "scorer_rating_confidences": self.rating_confidences,
        }

    def _add_tag(self, tag: str, reason: str | None, confidence: float | None) -> None:
        """Add a tag to the `feedback.scorer_tags` column array."""
        if len(self.tags) >= _MAX_TAGS_PER_ROW:
            logger.warning(
                'Exceeded max %d tags per scorer, skipping "%s"',
                _MAX_TAGS_PER_ROW,
                tag,
            )
            return
        if tag := self._sanitize_tag(tag):
            if tag in self.tags:
                logger.warning("Skipping duplicate tag '%s'", tag)
                return
            self.tags.append(tag)
            self.tags.sort()
        else:
            tag = _SCORER_EMPTY_TAG_KEY
        if reason := self._sanitize_reason(reason):
            self.tag_reasons[tag] = reason
        if isinstance(confidence, float):
            self.tag_confidences[tag] = confidence

    def _add_rating(
        self, rating: float, reason: str | None, confidence: float | None
    ) -> None:
        """Add a rating to the `feedback.scorer_ratings` column map."""
        if self.ratings:
            raise ValueError("Multiple ratings per scorer are not supported")
        self.ratings[_SCORER_RATING_MAP_KEY] = rating
        if reason := self._sanitize_reason(reason):
            self.rating_reasons[_SCORER_RATING_MAP_KEY] = reason
        if isinstance(confidence, float):
            self.rating_confidences[_SCORER_RATING_MAP_KEY] = confidence

    @staticmethod
    def _sanitize_tag(tag: str | None) -> str:
        """Strip forbidden chars, replace whitespace with dashes and coerce to lowercase."""
        if not tag:
            return ""
        tag = _SCORER_METADATA_CHARS_RE.sub("", tag)
        return re.sub(r"\s+", "-", tag.strip().lower())

    @staticmethod
    def _sanitize_reason(reason: str | None) -> str:
        """Strip forbidden chars."""
        if not reason:
            return ""
        reason = _SCORER_METADATA_CHARS_RE.sub("", reason).strip()
        return reason[:_MAX_REASON_LENGTH]
