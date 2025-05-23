# %% [markdown]
# # Advanced Evaluation Examples for the Workshop
#
# This notebook provides additional examples of using Weave's evaluation features
# for the Weave workshop, including the EvaluationLogger's dictionary identification pattern.

# %%
import asyncio
import json
from typing import Any
from datetime import datetime

from openai import OpenAI

import weave
from weave import Dataset, Evaluation, EvaluationLogger, Model

# Initialize Weave
weave.init("weave_workshop")

# %% [markdown]
# ## Example 1: Custom Scorer Class
#
# Sometimes you want to create reusable scorer classes with their own configuration.

# %%
from weave import Scorer


class LLMJudgeScorer(Scorer):
    """A scorer that uses an LLM to judge the quality of extractions"""

    model_name: str = "gpt-4o-mini"
    judge_prompt: str = """You are an expert evaluator of information extraction systems.

    Given an email and the extracted information, rate the extraction quality on a scale of 1-10.
    Consider:
    - Accuracy of extracted information
    - Completeness (did it miss anything important?)
    - Conciseness of the issue description

    Email: {email}

    Extracted Information:
    - Customer Name: {customer_name}
    - Product Model: {product_model}
    - Issue Description: {issue_description}

    Provide a score from 1-10 and a brief explanation.
    Return as JSON with fields: score (number), explanation (string)
    """

    @weave.op
    def score(self, email: str, output: dict[str, Any]) -> dict[str, Any]:
        """Score using LLM as judge"""
        client = OpenAI()

        prompt = self.judge_prompt.format(
            email=email,
            customer_name=output.get("customer_name", "N/A"),
            product_model=output.get("product_model", "N/A"),
            issue_description=output.get("issue_description", "N/A"),
        )

        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are an expert evaluator."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        return {
            "llm_judge_score": result["score"] / 10.0,  # Normalize to 0-1
            "llm_judge_explanation": result["explanation"],
        }


# %% [markdown]
# ## Example 2: Batch Evaluation with Progress Tracking


# %%
@weave.op
def batch_evaluate_with_progress(models: list[Model], dataset: Dataset, scorers: list):
    """Evaluate multiple models and show progress"""
    results = {}
    total_evaluations = len(models)

    for i, model in enumerate(models):
        model_name = getattr(model, "name", model.__class__.__name__)
        print(f"\n📊 Evaluating {model_name} ({i+1}/{total_evaluations})...")

        evaluation = Evaluation(
            dataset=dataset, scorers=scorers, name=f"Batch Evaluation - {model_name}"
        )

        # Run evaluation
        result = asyncio.run(evaluation.evaluate(model))
        results[model_name] = result

        print(f"✅ Completed {model_name}")

    return results


# %% [markdown]
# ## Example 3: Multi-Stage Evaluation Pipeline
#
# For complex evaluations, you might want to run different stages with different criteria.


# %%
class MultiStageEvaluator:
    """Run multi-stage evaluation with different criteria"""

    def __init__(self, model, dataset):
        self.model = model
        self.dataset = dataset
        self.logger = EvaluationLogger(
            model=model.__class__.__name__, dataset=dataset.name
        )

    @weave.op
    def evaluate_accuracy_stage(self, example):
        """Stage 1: Evaluate extraction accuracy"""
        output = self.model.predict(example["email"])

        pred_logger = self.logger.log_prediction(
            inputs={"email": example["email"]}, output=output.model_dump()
        )

        # Check exact matches
        for field in ["customer_name", "product_model"]:
            expected = example.get(f"expected_{field}", "")
            actual = getattr(output, field, "")
            match = expected.lower() == actual.lower()
            pred_logger.log_score(scorer=f"{field}_exact", score=match)

        return pred_logger

    @weave.op
    def evaluate_quality_stage(self, example, pred_logger):
        """Stage 2: Evaluate output quality"""
        output = self.model.predict(example["email"])

        # Check issue description quality
        issue_desc = output.issue_description

        # Length check (should be concise)
        is_concise = 10 <= len(issue_desc) <= 100
        pred_logger.log_score(scorer="description_concise", score=is_concise)

        # Contains key information
        email_lower = example["email"].lower()
        desc_lower = issue_desc.lower()

        # Simple keyword overlap check
        keywords = [word for word in desc_lower.split() if len(word) > 3]
        keyword_coverage = sum(1 for kw in keywords if kw in email_lower) / max(
            len(keywords), 1
        )
        pred_logger.log_score(scorer="keyword_coverage", score=keyword_coverage)

        pred_logger.finish()

    @weave.op
    def run_full_evaluation(self):
        """Run complete multi-stage evaluation"""
        print(f"🚀 Starting multi-stage evaluation for {self.model.__class__.__name__}")

        for example in self.dataset.rows:
            # Stage 1: Accuracy
            pred_logger = self.evaluate_accuracy_stage(example)

            # Stage 2: Quality
            self.evaluate_quality_stage(example, pred_logger)

        # Summary metrics
        self.logger.log_summary(
            {"evaluation_type": "multi_stage", "stages": ["accuracy", "quality"]}
        )

        print("✅ Multi-stage evaluation complete!")


# %% [markdown]
# ## Example 4: A/B Testing Framework
#
# Compare two models head-to-head on the same examples.


# %%
@weave.op
def ab_test_models(model_a: Model, model_b: Model, dataset: Dataset) -> dict[str, Any]:
    """Run A/B test between two models"""
    logger_a = EvaluationLogger(
        model=f"{model_a.__class__.__name__}_A", dataset=dataset.name
    )
    logger_b = EvaluationLogger(
        model=f"{model_b.__class__.__name__}_B", dataset=dataset.name
    )

    wins_a = 0
    wins_b = 0
    ties = 0

    for example in dataset.rows:
        # Get predictions from both models
        output_a = model_a.predict(example["email"])
        output_b = model_b.predict(example["email"])

        # Log predictions
        pred_a = logger_a.log_prediction(
            inputs={"email": example["email"]}, output=output_a.model_dump()
        )
        pred_b = logger_b.log_prediction(
            inputs={"email": example["email"]}, output=output_b.model_dump()
        )

        # Calculate scores for both
        score_a = 0
        score_b = 0

        for field in ["customer_name", "product_model", "issue_description"]:
            expected = example.get(f"expected_{field}", "")

            # Model A
            actual_a = getattr(output_a, field, "")
            if expected.lower() == actual_a.lower():
                score_a += 1
                pred_a.log_score(scorer=f"{field}_correct", score=True)
            else:
                pred_a.log_score(scorer=f"{field}_correct", score=False)

            # Model B
            actual_b = getattr(output_b, field, "")
            if expected.lower() == actual_b.lower():
                score_b += 1
                pred_b.log_score(scorer=f"{field}_correct", score=True)
            else:
                pred_b.log_score(scorer=f"{field}_correct", score=False)

        # Determine winner for this example
        if score_a > score_b:
            wins_a += 1
            pred_a.log_score(scorer="head_to_head", score=1)
            pred_b.log_score(scorer="head_to_head", score=0)
        elif score_b > score_a:
            wins_b += 1
            pred_a.log_score(scorer="head_to_head", score=0)
            pred_b.log_score(scorer="head_to_head", score=1)
        else:
            ties += 1
            pred_a.log_score(scorer="head_to_head", score=0.5)
            pred_b.log_score(scorer="head_to_head", score=0.5)

        pred_a.finish()
        pred_b.finish()

    # Log summaries
    total = len(dataset.rows)
    logger_a.log_summary({"ab_test_wins": wins_a, "ab_test_win_rate": wins_a / total})
    logger_b.log_summary({"ab_test_wins": wins_b, "ab_test_win_rate": wins_b / total})

    # Return results
    return {
        "model_a_wins": wins_a,
        "model_b_wins": wins_b,
        "ties": ties,
        "model_a_win_rate": wins_a / total,
        "model_b_win_rate": wins_b / total,
        "winner": "Model A"
        if wins_a > wins_b
        else ("Model B" if wins_b > wins_a else "Tie"),
    }


# %% [markdown]
# ## Example 5: Cross-Validation Style Evaluation
#
# Split your dataset and evaluate on different subsets.


# %%
@weave.op
def cross_validate_model(
    model: Model, dataset: Dataset, n_folds: int = 3
) -> list[dict]:
    """Perform k-fold cross-validation style evaluation"""
    rows = dataset.rows
    fold_size = len(rows) // n_folds
    results = []

    for fold in range(n_folds):
        # Create train/test split
        start_idx = fold * fold_size
        end_idx = start_idx + fold_size if fold < n_folds - 1 else len(rows)

        test_rows = rows[start_idx:end_idx]
        train_rows = rows[:start_idx] + rows[end_idx:]

        # Create fold dataset
        fold_dataset = Dataset(name=f"{dataset.name}_fold_{fold+1}", rows=test_rows)

        # Create fold-specific logger
        logger = EvaluationLogger(
            model=f"{model.__class__.__name__}_fold_{fold+1}", dataset=fold_dataset.name
        )

        # Evaluate on this fold
        fold_scores = []
        for example in test_rows:
            output = model.predict(example["email"])

            pred = logger.log_prediction(
                inputs={"email": example["email"]}, output=output.model_dump()
            )

            # Calculate accuracy
            correct_fields = 0
            total_fields = 3

            for field in ["customer_name", "product_model", "issue_description"]:
                expected = example.get(f"expected_{field}", "")
                actual = getattr(output, field, "")
                if expected.lower() == actual.lower():
                    correct_fields += 1
                    pred.log_score(scorer=f"{field}_match", score=True)
                else:
                    pred.log_score(scorer=f"{field}_match", score=False)

            accuracy = correct_fields / total_fields
            pred.log_score(scorer="accuracy", score=accuracy)
            fold_scores.append(accuracy)

            pred.finish()

        # Log fold summary
        avg_accuracy = sum(fold_scores) / len(fold_scores) if fold_scores else 0
        logger.log_summary(
            {
                "fold_number": fold + 1,
                "fold_size": len(test_rows),
                "average_accuracy": avg_accuracy,
            }
        )

        results.append(
            {
                "fold": fold + 1,
                "test_size": len(test_rows),
                "train_size": len(train_rows),
                "average_accuracy": avg_accuracy,
            }
        )

    # Calculate overall metrics
    overall_accuracy = sum(r["average_accuracy"] for r in results) / len(results)
    accuracy_std = (
        sum((r["average_accuracy"] - overall_accuracy) ** 2 for r in results)
        / len(results)
    ) ** 0.5

    print("\n📊 Cross-Validation Results:")
    print(f"Average Accuracy: {overall_accuracy:.3f} ± {accuracy_std:.3f}")
    for r in results:
        print(f"  Fold {r['fold']}: {r['average_accuracy']:.3f}")

    return results


# %% [markdown]
# ## Usage Examples
#
# Here's how you might use these advanced evaluation patterns in your workshop:

# %%
# Example usage (commented out to avoid execution)
"""
# 1. Using custom LLM Judge scorer
llm_judge = LLMJudgeScorer()
evaluation_with_judge = Evaluation(
    dataset=your_dataset,
    scorers=[exact_match_scorer, llm_judge],
    name="Evaluation with LLM Judge"
)

# 2. Running multi-stage evaluation
evaluator = MultiStageEvaluator(model=your_model, dataset=your_dataset)
evaluator.run_full_evaluation()

# 3. A/B Testing two models
results = ab_test_models(model_v1, model_v2, your_dataset)
print(f"A/B Test Winner: {results['winner']}")

# 4. Cross-validation
cv_results = cross_validate_model(your_model, your_dataset, n_folds=5)
"""

# %% [markdown]
# ## Key Takeaways for Advanced Evaluation
#
# 1. **Custom Scorers**: Create reusable scorer classes for complex evaluation logic
# 2. **Multi-Stage**: Break down evaluation into logical stages for better insights
# 3. **A/B Testing**: Compare models head-to-head on the same data
# 4. **Cross-Validation**: Get more robust evaluation metrics with multiple folds
# 5. **Progress Tracking**: Use EvaluationLogger for real-time progress updates
#
# These patterns help you build more sophisticated evaluation pipelines that go beyond simple accuracy metrics!


@weave.op
def evaluate_model(
    model: Model,
    dataset: Dataset,
    scorers: list[Scorer],
) -> dict[str, Any]:
    """Run evaluation on a model."""
    results = {}
    for scorer in scorers:
        score = scorer(model, dataset)
        results[scorer.__name__] = score
    return results


@weave.op
def compare_models(
    models: list[Model],
    dataset: Dataset,
    scorers: list[Scorer],
) -> dict[str, dict[str, Any]]:
    """Compare multiple models using the same evaluation."""
    results = {}
    for model in models:
        results[model.name] = evaluate_model(model, dataset, scorers)
    return results


# %% [markdown]
# ## Advanced EvaluationLogger Patterns with Rich Metadata
#
# Here's how to use dictionary identification for production-grade evaluation tracking:

# %%
def create_production_eval_logger(
    model_config: dict,
    experiment_name: str,
    dataset_info: dict
) -> EvaluationLogger:
    """Create an evaluation logger with rich metadata for production use."""
    
    # Rich model identification
    model_metadata = {
        "name": model_config.get("name", "unknown_model"),
        "version": model_config.get("version", "0.0.0"),
        "provider": model_config.get("provider", "openai"),
        "base_model": model_config.get("base_model", "gpt-3.5-turbo"),
        "parameters": {
            "temperature": model_config.get("temperature", 0.7),
            "max_tokens": model_config.get("max_tokens", 150),
            "top_p": model_config.get("top_p", 1.0),
        },
        "prompt_template": model_config.get("prompt_template_version", "v1"),
        "experiment": experiment_name,
        "deployed_at": model_config.get("deployed_at", datetime.now().isoformat()),
    }
    
    # Rich dataset identification
    dataset_metadata = {
        "name": dataset_info.get("name", "unknown_dataset"),
        "version": dataset_info.get("version", "1.0.0"),
        "source": dataset_info.get("source", "production"),
        "size": dataset_info.get("size", 0),
        "created_at": dataset_info.get("created_at", datetime.now().isoformat()),
        "filters": dataset_info.get("filters", {}),
        "split": dataset_info.get("split", "test"),
        "characteristics": dataset_info.get("characteristics", {})
    }
    
    return EvaluationLogger(
        model=model_metadata,
        dataset=dataset_metadata
    )

# Example usage
model_config = {
    "name": "customer_support_analyzer",
    "version": "2.1.0",
    "provider": "openai",
    "base_model": "gpt-4",
    "temperature": 0.3,
    "max_tokens": 200,
    "prompt_template_version": "v3_detailed",
    "deployed_at": "2024-01-15T10:00:00Z"
}

dataset_info = {
    "name": "support_emails_q1_2024",
    "version": "1.2.0",
    "source": "production_sampling",
    "size": 1000,
    "filters": {
        "date_range": "2024-01-01 to 2024-03-31",
        "language": "en",
        "region": "US"
    },
    "split": "test",
    "characteristics": {
        "avg_length": 150,
        "sentiment_distribution": {
            "positive": 0.2,
            "neutral": 0.3,
            "negative": 0.5
        }
    }
}

# Create logger with rich metadata
production_logger = create_production_eval_logger(
    model_config=model_config,
    experiment_name="q1_2024_performance_review",
    dataset_info=dataset_info
)

# %% [markdown]
# This rich metadata pattern enables:
# 1. **Easy filtering** in the Weave UI by any metadata field
# 2. **Version tracking** for both models and datasets
# 3. **Experiment grouping** to compare related evaluations
# 4. **Audit trails** with timestamps and deployment info
# 5. **Performance analysis** by correlating with model parameters
