from __future__ import annotations

import logging
import re
from typing import Annotated, Any

from pydantic import BaseModel, Field
from typing_extensions import Self

logger = logging.getLogger(__name__)

_MAX_TAGS_PER_ROW = 10
_MAX_TAG_LENGTH = 36
_MAX_REASON_LENGTH = 256

# Currently we allow scorers to emit a single numeric rating, which always uses this key.
# If we choose to allow multiple ratings in the future we can remove this constant.
SCORER_RATING_MAP_KEY = "_rating_"

# A scorer might give a reason for *not* tagging, which we assign to this sentinel.
SCORER_EMPTY_TAG_KEY = "_empty_"

# Regex for chars allowed in tags and reasons. Whitespace will be removed from tags separately.
_SCORER_METADATA_CHARS_RE = re.compile(r"[^0-9a-zA-Z \.,;\-&!@#$%?]")

_TagType = Annotated[str, Field(max_length=_MAX_TAG_LENGTH)]
_RatingType = Annotated[float, Field(ge=0.0, le=1.0)]


class ScorerOutputSchema(BaseModel):
    """Schema for a single scorer tag or rating. Extra keys are ignored."""

    value: _TagType | _RatingType
    reason: str | None = Field(default=None, max_length=_MAX_REASON_LENGTH)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ScorerOutputGroup(BaseModel):
    """Schema for a list of scorer tag or rating outputs."""

    scores: list[ScorerOutputSchema]

    @classmethod
    def from_scorer_output(cls, obj: Any) -> Self:
        """Parse and validate scorer output in any supported format.

        Supported formats:
        - A single score payload:  `{"value": "ok"}`
        - A list of scores:        `[{"value": "ok"}, {"value": 0.5}]`
        - A nested list of scores: `{"scores": [{"value": 0.9}]}`
        """
        if isinstance(obj, list):
            return cls.model_validate({"scores": obj})
        if not isinstance(obj, dict):
            raise TypeError(f"Invalid scorer output type: {type(obj).__name__}")
        if isinstance(obj.get("scores"), list):
            return cls.model_validate(obj)
        return cls.model_validate({"scores": [obj]})


class ScorerFeedbackColumns(BaseModel):
    """Represents typed scorer feedback columns in the DB.

    Includes helper methods for normalizing raw scorer output.
    """

    tags: list[str] = Field(default_factory=list)
    ratings: dict[str, float] = Field(default_factory=dict)
    tag_reasons: dict[str, str] = Field(default_factory=dict)
    tag_confidences: dict[str, float] = Field(default_factory=dict)
    rating_reasons: dict[str, str] = Field(default_factory=dict)
    rating_confidences: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def from_scorer_output_group(
        cls, group: ScorerOutputGroup
    ) -> Self:
        """Return normalized typed scorer feedback columns from scorer output."""
        cols = cls()

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

    def _add_tag(self, tag: str, reason: str | None, confidence: float | None) -> None:
        """Add a tag to the typed scorer feedback columns."""
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
            self.tags.sort() # Inefficient, but good enough for very short lists
        else:
            tag = SCORER_EMPTY_TAG_KEY
        if reason := self._sanitize_reason(reason):
            self.tag_reasons[tag] = reason
        if isinstance(confidence, float):
            self.tag_confidences[tag] = confidence

    def _add_rating(
        self, rating: float, reason: str | None, confidence: float | None
    ) -> None:
        """Add a rating to the typed scorer feedback columns."""
        if self.ratings:
            raise ValueError("Multiple ratings per scorer are not supported")
        self.ratings[SCORER_RATING_MAP_KEY] = rating
        if reason := self._sanitize_reason(reason):
            self.rating_reasons[SCORER_RATING_MAP_KEY] = reason
        if isinstance(confidence, float):
            self.rating_confidences[SCORER_RATING_MAP_KEY] = confidence

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
