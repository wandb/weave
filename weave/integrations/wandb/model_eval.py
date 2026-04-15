"""ModelEvaluationLogger: EvaluationLogger subclass for W&B model evaluation results."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from weave.evaluation.eval_imperative import EvaluationLogger, ScoreType
from weave.integrations.wandb.media import _WANDB_AVAILABLE, _unwrap_value
from weave.trace_server.constants import WEAVE_EVAL_META_ATTR_KEY

MODEL_EVAL_KEY = "model_eval"

if TYPE_CHECKING:
    import wandb



class ModelEvaluationLogger(EvaluationLogger):
    """An EvaluationLogger specialised for logging W&B model evaluation results.

    Marks the eval as a model eval (to trigger Model Evals UI panel).

    You can use it just like an EvaluationLogger, or you can use the wandb.Table
    adapter via log_table:

    Example::

        import wandb
        import weave
        from weave.integrations.wandb import ModelEvaluationLogger

        with wandb.init(project="my-project", config={"epochs": 10})
            with weave.init("my-project")
                for epoch in range epochs:

                    # ... training/validation code

                    table = wandb.Table(
                        columns=["image", "truth", "predicted", "confidence", "correct", "calibrated_score"],
                        data=[...],
                    )

                    ev = ModelEvaluationLogger(name="results")
                    ev.log_table(
                        table,
                        input_columns=["image", "truth"],
                        output_columns=["predicted", "confidence"],
                        score_columns=["correct", "calibrated_score"],
                    )
                    ev.log_summary()
                    wandb.log({"epoch"}: epoch)
    """

    @property
    def attributes(self) -> dict[str, Any]:
        base = super().attributes
        meta = dict(base[WEAVE_EVAL_META_ATTR_KEY])
        meta[MODEL_EVAL_KEY] = True
        base[WEAVE_EVAL_META_ATTR_KEY] = meta
        return base

    def __init__(self, name: str, **kwargs: object) -> None:
        """Create a ModelEvaluationLogger.

        Args:
            name: Required evaluation used by the Model Evals UI panel.
            **kwargs: Additional keyword arguments forwarded to EvaluationLogger, e.g.
                eval_attributes
        """
        super().__init__(name=name, **kwargs)

    def log_table(
        self,
        table: wandb.Table,
        input_columns: list[str] | None = None,
        output_columns: list[str] | None = None,
        score_columns: list[str] | None = None,
    ) -> None:
        """Convert and log all rows of a wandb.Table as evaluation examples.

        Each row becomes one logged example. wandb media types are converted to
        their Weave-native equivalents before logging:

        - ``wandb.Image``  → ``PIL.Image.Image`` (falls back to ``weave.Content``)

        Column validation requires every table column to be assigned to exactly
        one of the three lists. Any omitted list defaults to empty.

        Args:
            table: A ``wandb.Table`` instance.
            input_columns: Column names to include in the ``inputs`` dict.
                Defaults to no input columns.
            output_columns: Column names to include in the ``output`` dict.
                Defaults to no output columns.
            score_columns: Column names to include in the ``scores`` dict.
                Defaults to no score columns.

        Raises:
            ImportError: If wandb is not installed.
            ValueError: If column validation fails or a media value has no
                accessible data.
            TypeError: If a cell contains an unsupported wandb media type.
        """
        if not _WANDB_AVAILABLE:
            raise ImportError(
                "wandb must be installed to use ModelEvaluationLogger.log_table. "
                "Install it with: pip install wandb"
            )

        input_columns = input_columns or []
        output_columns = output_columns or []
        score_columns = score_columns or []

        table_columns: list[str] = list(table.columns)
        all_listed = set(input_columns) | set(output_columns) | set(score_columns)
        table_column_set = set(table_columns)

        unknown = all_listed - table_column_set
        if unknown:
            raise ValueError(
                "The following columns were listed but do not exist in the table: "
                f"{sorted(unknown)}"
            )

        unaccounted = table_column_set - all_listed
        if unaccounted:
            raise ValueError(
                "The following table columns are not listed in input_columns, "
                f"output_columns, or score_columns: {sorted(unaccounted)}. "
                "Every column must be assigned to exactly one list."
            )

        seen: set[str] = set()
        for col in input_columns + output_columns + score_columns:
            if col in seen:
                warnings.warn(
                    f"Column {col!r} appears in more than one column list; "
                    "it will be included in all matching dicts.",
                    stacklevel=2,
                )
            seen.add(col)

        col_index: dict[str, int] = {name: i for i, name in enumerate(table_columns)}
        warned: set[type] = set()

        for row in table.data:
            inputs: dict[str, Any] = {
                col: _unwrap_value(row[col_index[col]], col, warned) for col in input_columns
            }
            output: dict[str, Any] = {
                col: _unwrap_value(row[col_index[col]], col, warned) for col in output_columns
            }
            scores: dict[str, ScoreType] = {
                col: _unwrap_value(row[col_index[col]], col, warned)  # type: ignore[assignment]
                for col in score_columns
            }
            self.log_example(inputs=inputs, output=output, scores=scores)
