from typing import Any, Optional, Union

from pydantic import Field

import weave


class BLEUScorer(weave.Scorer):
    """A Scorer that computes the BLEU score using SacreBLEU."""

    # Optional configuration parameters
    lowercase: bool = Field(
        default=False, description="If True, use case-insensitive matching."
    )
    tokenize: Optional[str] = Field(
        default=None,
        description=(
            "The tokenizer to use. If None, defaults to SacreBLEU's default tokenizer."
        ),
    )
    smooth_method: str = Field(
        default="exp",
        description="Smoothing method to use: 'none', 'floor', 'add-k', or 'exp'.",
    )
    smooth_value: Optional[float] = Field(
        default=None,
        description="Smoothing value for 'floor' and 'add-k' methods.",
    )
    max_ngram_order: int = Field(
        default=4, description="Maximum n-gram order for BLEU calculation."
    )
    effective_order: bool = Field(
        default=True,  # because we are doing sentence-level BLEU in the `score` method
        description="If True, use effective order for sentence-level BLEU.",
    )
    bleu: Any = Field(default=None, exclude=True)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        try:
            from sacrebleu.metrics import BLEU

            self.bleu = BLEU(
                lowercase=self.lowercase,
                tokenize=self.tokenize,
                smooth_method=self.smooth_method,
                smooth_value=self.smooth_value,
                max_ngram_order=self.max_ngram_order,
                effective_order=self.effective_order,
            )
        except ImportError:
            raise ImportError(
                "BLEUScorer requires the sacrebleu library to be installed. "
                "Please install it with `pip install sacrebleu`."
            )

    @weave.op()
    def score(
        self, ground_truths: list[str], output: str
    ) -> dict[str, Union[str, float, list[str]]]:
        """Computes the BLEU score for a single hypothesis and reference(s)."""
        # Ensure that the reference is a list of strings
        if isinstance(ground_truths, str):
            ground_truths = [ground_truths]

        assert isinstance(
            ground_truths, list
        ), "`ground_truths` must be a list of strings."

        # Compute the individual/sentence-level BLEU score
        score = self.bleu.sentence_score(output, ground_truths)

        return {
            "sentence_bleu": score.score,
            "sentence_bp": score.bp,
            "output_pred": output,
            "output_refs": ground_truths,
        }

    @weave.op()
    def summarize(self, score_rows: list[dict]) -> dict:
        if not score_rows:
            return {}

        assert all(
            isinstance(x, dict) for x in score_rows
        ), "All score rows must be dictionaries"

        # Compute average sentence-level BLEU score
        sentence_bleu = sum(x["sentence_bleu"] for x in score_rows) / len(score_rows)

        # Compute corpus-level BLEU score
        sys_list = [x["output_pred"] for x in score_rows]
        refs_list = [x["output_refs"] for x in score_rows]

        corpus_bleu = self.bleu.corpus_score(sys_list, refs_list)

        return {
            "corpus_level": {
                "bleu": corpus_bleu.score,
                "brevity_penalty": corpus_bleu.bp,
            },
            "sentence_level": {"bleu": sentence_bleu},
        }
