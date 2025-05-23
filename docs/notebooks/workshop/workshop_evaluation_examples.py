# %% [markdown]
# # 🚀 Advanced Weave Evaluation Patterns
#
# <img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
#
# Welcome to the advanced evaluation patterns workshop! This notebook extends the main Weave workshop
# with sophisticated evaluation techniques for production use cases.
#
# **What you'll learn:**
# - 🎯 **Custom Scorers**: Build domain-specific evaluation metrics
# - 📊 **Multi-Stage Evaluation**: Break complex evaluations into stages
# - 🏃 **A/B Testing**: Statistical comparison of models
# - 🔄 **Cross-Validation**: Robust evaluation with data splits
# - 🏭 **Production Patterns**: Real-world evaluation workflows

# %% [markdown]
# ## 🔑 Prerequisites & Setup
#
# Run this notebook after completing the main Weave workshop, or as a standalone advanced tutorial.

# %%
# Install dependencies (for Colab compatibility)
# %pip install wandb weave openai pydantic nest_asyncio litellm -qqq

import os
import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional

import nest_asyncio
from pydantic import BaseModel, Field

import weave
from weave import Dataset, Evaluation, EvaluationLogger, Model, Scorer

# Enable nested asyncio for notebooks
nest_asyncio.apply()

# 🔑 Setup API keys
print("📝 Setting up environment...")

# OpenAI API key setup
if not os.environ.get("OPENAI_API_KEY"):
    print("⚠️ OpenAI API key not found!")
    print("Set it with: os.environ['OPENAI_API_KEY'] = 'your-key-here'")
    # For Colab, you might use:
    # from google.colab import userdata
    # os.environ["OPENAI_API_KEY"] = userdata.get('OPENAI_API_KEY')
else:
    print("✅ OpenAI API key found")

# Initialize Weave
print("🐝 Initializing Weave...")
weave_client = weave.init("advanced-evaluation-workshop")
print("✅ Setup complete!")

# %% [markdown]
# ## 📋 Shared Data Models
#
# We'll use the same models from the main workshop for consistency.


# %%
# Define our data structures (from main workshop)
class CustomerEmail(BaseModel):
    """Basic customer email analysis."""

    customer_name: str
    product: str
    issue: str
    sentiment: str = Field(description="positive, neutral, or negative")


class DetailedCustomerEmail(BaseModel):
    """Extended analysis with more fields."""

    customer_name: str
    customer_title: Optional[str] = Field(description="Job title if mentioned")
    company: Optional[str] = Field(description="Company name if mentioned")
    product: str
    product_version: Optional[str] = Field(description="Specific version number")
    issue: str
    issue_category: str = Field(
        description="technical, billing, feature_request, or other"
    )
    severity: str = Field(description="critical, high, medium, or low")
    sentiment: str = Field(description="positive, neutral, or negative")


# Create a sample dataset for our examples
print("📊 Creating sample dataset...")
advanced_dataset = Dataset(
    name="advanced_support_emails",
    rows=[
        {
            "email": "Hi Support, I'm Sarah Chen, CTO at TechCorp. Our Enterprise CloudSync v3.2 cluster is experiencing critical latency issues affecting 5000+ users. Need immediate assistance!",
            "expected": {
                "customer_name": "Sarah Chen",
                "severity": "critical",
                "product": "Enterprise CloudSync v3.2",
                "issue_category": "technical",
                "company": "TechCorp",
            },
        },
        {
            "email": "Hello, this is Mike Johnson. I'd like to request a feature for DataProcessor Pro - ability to export to Parquet format. Not urgent but would be very helpful.",
            "expected": {
                "customer_name": "Mike Johnson",
                "severity": "low",
                "product": "DataProcessor Pro",
                "issue_category": "feature_request",
                "sentiment": "positive",
            },
        },
        {
            "email": "Billing issue! We were charged twice for CloudVault licenses last month. Please refund ASAP. - Janet Williams, Accounting Manager at FinanceInc",
            "expected": {
                "customer_name": "Janet Williams",
                "severity": "high",
                "product": "CloudVault",
                "issue_category": "billing",
                "company": "FinanceInc",
            },
        },
    ],
)
print(f"✅ Created dataset with {len(advanced_dataset.rows)} examples")

# %% [markdown]
# ## 🎯 Example 1: Domain-Specific Custom Scorers
#
# Build sophisticated scorers that understand your business logic.

# %%
print("=" * 70)
print("🎯 EXAMPLE 1: Domain-Specific Custom Scorers")
print("=" * 70)


class BusinessImpactScorer(Scorer):
    """Score based on potential business impact of the issue."""

    @weave.op
    def score(self, expected: dict, output: DetailedCustomerEmail) -> dict[str, Any]:
        """Calculate business impact score based on multiple factors."""
        impact_score = 0.0
        factors = []

        # 1. Severity weight (40%)
        severity_weights = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.1}
        severity_score = severity_weights.get(output.severity, 0.5) * 0.4
        impact_score += severity_score
        factors.append(f"Severity ({output.severity}): {severity_score:.2f}")

        # 2. Customer type weight (30%)
        customer_score = 0.0
        if output.company:
            customer_score += 0.2  # B2B customer
            if "enterprise" in output.product.lower():
                customer_score += 0.1  # Enterprise product
        else:
            customer_score += 0.1  # B2C customer
        impact_score += customer_score
        factors.append(f"Customer type: {customer_score:.2f}")

        # 3. Issue category weight (30%)
        category_weights = {
            "technical": 0.25,  # Can affect operations
            "billing": 0.20,  # Revenue impact
            "feature_request": 0.05,  # Future value
            "other": 0.10,
        }
        category_score = category_weights.get(output.issue_category, 0.1) * 1.0
        impact_score += category_score
        factors.append(f"Category ({output.issue_category}): {category_score:.2f}")

        # Business rules
        requires_escalation = (
            output.severity in ["critical", "high"]
            or output.issue_category == "billing"
            or (output.company and "enterprise" in output.product.lower())
        )

        return {
            "business_impact_score": impact_score,
            "impact_factors": factors,
            "requires_escalation": requires_escalation,
            "priority_level": "P1"
            if impact_score > 0.7
            else ("P2" if impact_score > 0.4 else "P3"),
        }


class SLAComplianceScorer(Scorer):
    """Check if response meets SLA requirements."""

    def __init__(self, sla_rules: Optional[Dict] = None):
        """Initialize with SLA rules."""
        self.sla_rules = sla_rules or {
            "critical": {"response_time_hours": 1, "resolution_time_hours": 4},
            "high": {"response_time_hours": 4, "resolution_time_hours": 24},
            "medium": {"response_time_hours": 24, "resolution_time_hours": 72},
            "low": {"response_time_hours": 72, "resolution_time_hours": 168},
        }

    @weave.op
    def score(
        self, output: DetailedCustomerEmail, response_time_hours: float = 0
    ) -> dict[str, Any]:
        """Check SLA compliance."""
        sla = self.sla_rules.get(output.severity, self.sla_rules["medium"])

        response_sla_met = response_time_hours <= sla["response_time_hours"]
        sla_margin = sla["response_time_hours"] - response_time_hours

        return {
            "sla_compliance": response_sla_met,
            "response_time_hours": response_time_hours,
            "sla_limit_hours": sla["response_time_hours"],
            "sla_margin_hours": sla_margin,
            "severity": output.severity,
            "requires_immediate_action": sla_margin < 0.5 and not response_sla_met,
        }


# Test the custom scorers
print("\n🧪 Testing Business Impact Scorer...")


# Create a simple model for testing
class SimpleAnalyzer(Model):
    """Simple analyzer for testing scorers."""

    @weave.op
    def predict(self, email: str) -> DetailedCustomerEmail:
        """Simplified analysis for demonstration."""
        # In real scenarios, this would use an LLM
        if "critical" in email.lower() or "immediate" in email.lower():
            severity = "critical"
        elif "asap" in email.lower() or "urgent" in email.lower():
            severity = "high"
        else:
            severity = "medium"

        return DetailedCustomerEmail(
            customer_name="Test User",
            product="Test Product",
            issue="Test issue from email",
            issue_category="technical" if "technical" in email.lower() else "other",
            severity=severity,
            sentiment="negative" if severity in ["critical", "high"] else "neutral",
            company="TestCorp" if "corp" in email.lower() else None,
        )


# Run evaluation with custom scorers
model = SimpleAnalyzer()
business_scorer = BusinessImpactScorer()
sla_scorer = SLAComplianceScorer()

print("\n📊 Running evaluation with custom scorers...")
custom_eval = Evaluation(
    name="business_impact_evaluation",
    dataset=advanced_dataset,
    scorers=[business_scorer],
)

# Note: For full execution, you would run:
# results = asyncio.run(custom_eval.evaluate(model))
print("✅ Custom scorers configured and ready!")

# %% [markdown]
# ## 🔄 Example 2: Multi-Stage Evaluation Pipeline
#
# Break complex evaluations into logical stages for better insights.

# %%
print("\n" + "=" * 70)
print("🔄 EXAMPLE 2: Multi-Stage Evaluation Pipeline")
print("=" * 70)


class MultiStageEvaluator:
    """Sophisticated multi-stage evaluation with detailed tracking."""

    def __init__(self, model: Model, dataset: Dataset):
        self.model = model
        self.dataset = dataset
        # Use rich metadata for the model
        model_metadata = {
            "name": model.__class__.__name__,
            "version": "1.0.0",
            "evaluation_type": "multi_stage",
            "stages": ["extraction", "accuracy", "quality", "business_logic"],
        }
        self.logger = EvaluationLogger(
            model=model_metadata, dataset=f"{dataset.name}_multistage"
        )
        self.stage_results = {}

    @weave.op
    def stage1_extraction_completeness(self, example: dict) -> dict:
        """Stage 1: Check if all required fields are extracted."""
        print("\n  🔍 Stage 1: Extraction Completeness")

        output = self.model.predict(example["email"])
        pred_logger = self.logger.log_prediction(
            inputs={"email": example["email"]}, output=output.model_dump()
        )

        # Check required fields
        required_fields = ["customer_name", "product", "issue", "severity", "sentiment"]
        optional_fields = ["company", "customer_title", "product_version"]

        required_complete = 0
        optional_complete = 0
        missing_fields = []

        for field in required_fields:
            value = getattr(output, field, None)
            if value and value != "Unknown":
                required_complete += 1
            else:
                missing_fields.append(field)

        for field in optional_fields:
            value = getattr(output, field, None)
            if value:
                optional_complete += 1

        completeness_score = (required_complete / len(required_fields)) * 0.8 + (
            optional_complete / len(optional_fields)
        ) * 0.2

        pred_logger.log_score(scorer="completeness", score=completeness_score)
        pred_logger.log_score(scorer="missing_fields_count", score=len(missing_fields))

        self.stage_results["extraction"] = {
            "completeness": completeness_score,
            "missing_fields": missing_fields,
        }

        print(f"    Completeness: {completeness_score:.2%}")
        print(f"    Missing fields: {missing_fields if missing_fields else 'None'}")

        return pred_logger

    @weave.op
    def stage2_accuracy_check(self, example: dict, pred_logger) -> None:
        """Stage 2: Check accuracy against expected values."""
        print("  🎯 Stage 2: Accuracy Check")

        output = self.model.predict(example["email"])
        expected = example.get("expected", {})

        accuracy_scores = {}

        # Check each expected field
        for field, expected_value in expected.items():
            actual_value = getattr(output, field, None)
            if actual_value:
                # Exact match or close enough
                is_correct = str(actual_value).lower() == str(expected_value).lower()
                accuracy_scores[field] = 1.0 if is_correct else 0.0
                pred_logger.log_score(
                    scorer=f"{field}_accuracy", score=accuracy_scores[field]
                )

        overall_accuracy = (
            sum(accuracy_scores.values()) / len(accuracy_scores)
            if accuracy_scores
            else 0
        )
        pred_logger.log_score(scorer="overall_accuracy", score=overall_accuracy)

        self.stage_results["accuracy"] = {
            "overall": overall_accuracy,
            "per_field": accuracy_scores,
        }

        print(f"    Overall accuracy: {overall_accuracy:.2%}")
        print(f"    Per-field: {accuracy_scores}")

    @weave.op
    def stage3_quality_assessment(self, example: dict, pred_logger) -> None:
        """Stage 3: Assess quality of extraction."""
        print("  📏 Stage 3: Quality Assessment")

        output = self.model.predict(example["email"])

        quality_metrics = {"specificity": 0.0, "consistency": 0.0, "actionability": 0.0}

        # Specificity: Are extracted values specific enough?
        if output.product and any(char.isdigit() for char in output.product):
            quality_metrics["specificity"] += 0.5  # Has version info
        if output.issue and len(output.issue) > 50:
            quality_metrics["specificity"] += 0.5  # Detailed description

        # Consistency: Do severity and sentiment align?
        severity_sentiment_map = {
            "critical": "negative",
            "high": "negative",
            "medium": "neutral",
            "low": "positive",
        }
        expected_sentiment = severity_sentiment_map.get(output.severity, "neutral")
        if output.sentiment == expected_sentiment:
            quality_metrics["consistency"] = 1.0

        # Actionability: Can we route this effectively?
        if output.severity and output.issue_category:
            quality_metrics["actionability"] = 1.0

        for metric, score in quality_metrics.items():
            pred_logger.log_score(scorer=f"quality_{metric}", score=score)

        overall_quality = sum(quality_metrics.values()) / len(quality_metrics)
        pred_logger.log_score(scorer="overall_quality", score=overall_quality)

        self.stage_results["quality"] = quality_metrics

        print(f"    Overall quality: {overall_quality:.2%}")
        print(f"    Metrics: {quality_metrics}")

    @weave.op
    def run_full_evaluation(self) -> dict:
        """Run all evaluation stages."""
        print("\n🚀 Starting Multi-Stage Evaluation")
        print(f"   Model: {self.model.__class__.__name__}")
        print(f"   Dataset: {self.dataset.name} ({len(self.dataset.rows)} examples)")

        all_results = []

        for i, example in enumerate(self.dataset.rows):
            print(f"\n📧 Example {i+1}/{len(self.dataset.rows)}")
            print(f"   Email preview: {example['email'][:80]}...")

            # Run all stages
            pred_logger = self.stage1_extraction_completeness(example)
            self.stage2_accuracy_check(example, pred_logger)
            self.stage3_quality_assessment(example, pred_logger)

            pred_logger.finish()
            all_results.append(self.stage_results.copy())

        # Calculate aggregate metrics
        aggregate_metrics = {
            "avg_completeness": statistics.mean(
                [r["extraction"]["completeness"] for r in all_results]
            ),
            "avg_accuracy": statistics.mean(
                [r["accuracy"]["overall"] for r in all_results]
            ),
            "avg_quality": statistics.mean(
                [r["quality"][m] for r in all_results for m in r["quality"]]
            )
            / 3,
        }

        # Log summary
        self.logger.log_summary(
            {
                "total_examples": len(self.dataset.rows),
                "aggregate_metrics": aggregate_metrics,
                "evaluation_completed": datetime.now().isoformat(),
            }
        )

        print("\n📊 Evaluation Complete!")
        print(f"   Average Completeness: {aggregate_metrics['avg_completeness']:.2%}")
        print(f"   Average Accuracy: {aggregate_metrics['avg_accuracy']:.2%}")
        print(f"   Average Quality: {aggregate_metrics['avg_quality']:.2%}")

        return aggregate_metrics


# Demonstrate multi-stage evaluation
evaluator = MultiStageEvaluator(model, advanced_dataset)
# To run: evaluator.run_full_evaluation()
print("\n✅ Multi-stage evaluator ready!")

# %% [markdown]
# ## 🏃 Example 3: Statistical A/B Testing
#
# Compare models with statistical rigor.

# %%
print("\n" + "=" * 70)
print("🏃 EXAMPLE 3: Statistical A/B Testing")
print("=" * 70)


@weave.op
def statistical_ab_test(
    model_a: Model, model_b: Model, dataset: Dataset, confidence_level: float = 0.95
) -> dict[str, Any]:
    """Perform A/B test with statistical significance testing."""
    print("\n🔬 Running Statistical A/B Test")
    print(f"   Model A: {model_a.__class__.__name__}")
    print(f"   Model B: {model_b.__class__.__name__}")
    print(f"   Confidence Level: {confidence_level:.0%}")

    # Create loggers with rich metadata
    logger_a = EvaluationLogger(
        model={
            "name": f"{model_a.__class__.__name__}",
            "variant": "A",
            "test_id": f"ab_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        },
        dataset=f"{dataset.name}_ab_test",
    )
    logger_b = EvaluationLogger(
        model={
            "name": f"{model_b.__class__.__name__}",
            "variant": "B",
            "test_id": f"ab_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        },
        dataset=f"{dataset.name}_ab_test",
    )

    # Collect scores for statistical analysis
    scores_a = []
    scores_b = []
    head_to_head = {"a_wins": 0, "b_wins": 0, "ties": 0}

    print(f"\n📊 Processing {len(dataset.rows)} examples...")

    for i, example in enumerate(dataset.rows):
        # Get predictions
        output_a = model_a.predict(example["email"])
        output_b = model_b.predict(example["email"])

        # Log predictions
        pred_a = logger_a.log_prediction(
            inputs={"email": example["email"]}, output=output_a.model_dump()
        )
        pred_b = logger_b.log_prediction(
            inputs={"email": example["email"]}, output=output_b.model_dump()
        )

        # Score each model (simplified scoring for demo)
        score_a = 0
        score_b = 0

        # Basic scoring: check key fields
        if output_a.customer_name and output_a.customer_name != "Unknown":
            score_a += 0.25
        if output_b.customer_name and output_b.customer_name != "Unknown":
            score_b += 0.25

        if output_a.severity in ["critical", "high", "medium", "low"]:
            score_a += 0.25
        if output_b.severity in ["critical", "high", "medium", "low"]:
            score_b += 0.25

        if len(output_a.issue) > 20:
            score_a += 0.25
        if len(output_b.issue) > 20:
            score_b += 0.25

        if output_a.issue_category in ["technical", "billing", "feature_request"]:
            score_a += 0.25
        if output_b.issue_category in ["technical", "billing", "feature_request"]:
            score_b += 0.25

        scores_a.append(score_a)
        scores_b.append(score_b)

        # Head-to-head comparison
        if score_a > score_b:
            head_to_head["a_wins"] += 1
        elif score_b > score_a:
            head_to_head["b_wins"] += 1
        else:
            head_to_head["ties"] += 1

        pred_a.log_score(scorer="quality_score", score=score_a)
        pred_b.log_score(scorer="quality_score", score=score_b)

        pred_a.finish()
        pred_b.finish()

    # Statistical analysis
    import statistics as stats

    mean_a = stats.mean(scores_a)
    mean_b = stats.mean(scores_b)
    std_a = stats.stdev(scores_a) if len(scores_a) > 1 else 0
    std_b = stats.stdev(scores_b) if len(scores_b) > 1 else 0

    # Simple t-test approximation (in production, use scipy.stats)
    n = len(scores_a)
    score_diff = mean_a - mean_b
    pooled_std = ((std_a**2 + std_b**2) / 2) ** 0.5
    t_statistic = score_diff / (pooled_std / (n**0.5)) if pooled_std > 0 else 0

    # Approximate p-value (simplified)
    is_significant = abs(t_statistic) > 1.96  # ~95% confidence

    results = {
        "model_a": {
            "mean_score": mean_a,
            "std_dev": std_a,
            "wins": head_to_head["a_wins"],
        },
        "model_b": {
            "mean_score": mean_b,
            "std_dev": std_b,
            "wins": head_to_head["b_wins"],
        },
        "comparison": {
            "score_difference": score_diff,
            "t_statistic": t_statistic,
            "is_significant": is_significant,
            "ties": head_to_head["ties"],
            "winner": "Model A" if score_diff > 0 else "Model B",
            "confidence": "High" if is_significant else "Low",
        },
    }

    # Log summaries
    logger_a.log_summary(
        {
            "mean_score": mean_a,
            "wins": head_to_head["a_wins"],
            "win_rate": head_to_head["a_wins"] / n,
        }
    )
    logger_b.log_summary(
        {
            "mean_score": mean_b,
            "wins": head_to_head["b_wins"],
            "win_rate": head_to_head["b_wins"] / n,
        }
    )

    print("\n📈 Results:")
    print(f"   Model A: {mean_a:.3f} ± {std_a:.3f}")
    print(f"   Model B: {mean_b:.3f} ± {std_b:.3f}")
    print(f"   Difference: {score_diff:.3f}")
    print(f"   Statistical Significance: {'YES' if is_significant else 'NO'}")
    print(
        f"   Winner: {results['comparison']['winner']} ({results['comparison']['confidence']} confidence)"
    )

    return results


# Create a second model for comparison
class ImprovedAnalyzer(SimpleAnalyzer):
    """Slightly better analyzer for A/B testing."""

    @weave.op
    def predict(self, email: str) -> DetailedCustomerEmail:
        """Improved analysis."""
        base_result = super().predict(email)
        # Add some improvements
        if "enterprise" in email.lower():
            base_result.product = "Enterprise " + base_result.product
        if "billing" in email.lower():
            base_result.issue_category = "billing"
        return base_result


model_b = ImprovedAnalyzer()
print("\n✅ A/B testing framework ready!")
# To run: statistical_ab_test(model, model_b, advanced_dataset)

# %% [markdown]
# ## 🔄 Example 4: Cross-Validation Evaluation
#
# Ensure robust evaluation with k-fold cross-validation.

# %%
print("\n" + "=" * 70)
print("🔄 EXAMPLE 4: Cross-Validation Evaluation")
print("=" * 70)


@weave.op
def cross_validate_model(
    model: Model, dataset: Dataset, n_folds: int = 3, stratify_by: Optional[str] = None
) -> dict[str, Any]:
    """Perform k-fold cross-validation with optional stratification."""
    print(f"\n🔄 Running {n_folds}-Fold Cross-Validation")
    print(f"   Model: {model.__class__.__name__}")
    print(f"   Dataset: {dataset.name} ({len(dataset.rows)} examples)")

    rows = dataset.rows
    fold_size = len(rows) // n_folds
    fold_results = []

    # Shuffle for randomness (in production, use a fixed seed for reproducibility)
    import random

    shuffled_rows = rows.copy()
    random.shuffle(shuffled_rows)

    for fold in range(n_folds):
        print(f"\n📁 Fold {fold + 1}/{n_folds}")

        # Create train/test split
        start_idx = fold * fold_size
        end_idx = start_idx + fold_size if fold < n_folds - 1 else len(shuffled_rows)

        test_rows = shuffled_rows[start_idx:end_idx]
        train_rows = shuffled_rows[:start_idx] + shuffled_rows[end_idx:]

        print(f"   Train: {len(train_rows)} examples")
        print(f"   Test: {len(test_rows)} examples")

        # Create fold dataset
        fold_dataset = Dataset(name=f"{dataset.name}_fold_{fold+1}", rows=test_rows)

        # Create fold-specific logger with metadata
        logger = EvaluationLogger(
            model={
                "name": model.__class__.__name__,
                "cross_validation": {
                    "fold": fold + 1,
                    "total_folds": n_folds,
                    "train_size": len(train_rows),
                    "test_size": len(test_rows),
                },
            },
            dataset=f"{dataset.name}_cv_fold_{fold+1}",
        )

        # Evaluate on this fold
        fold_scores = []
        fold_metrics = {"completeness": [], "accuracy": [], "consistency": []}

        for example in test_rows:
            output = model.predict(example["email"])

            pred = logger.log_prediction(
                inputs={"email": example["email"]}, output=output.model_dump()
            )

            # Calculate various metrics
            score = 0.0

            # Completeness
            if output.customer_name and output.customer_name != "Unknown":
                score += 0.25
                fold_metrics["completeness"].append(1.0)
            else:
                fold_metrics["completeness"].append(0.0)

            # Basic accuracy (simplified)
            if output.severity in ["critical", "high", "medium", "low"]:
                score += 0.25
                fold_metrics["accuracy"].append(1.0)
            else:
                fold_metrics["accuracy"].append(0.0)

            # Consistency check
            if (
                output.severity in ["critical", "high"]
                and output.sentiment == "negative"
            ) or (
                output.severity == "low" and output.sentiment in ["positive", "neutral"]
            ):
                score += 0.25
                fold_metrics["consistency"].append(1.0)
            else:
                fold_metrics["consistency"].append(0.0)

            fold_scores.append(score)
            pred.log_score(scorer="overall_score", score=score)
            pred.finish()

        # Calculate fold statistics
        fold_mean = statistics.mean(fold_scores)
        fold_std = statistics.stdev(fold_scores) if len(fold_scores) > 1 else 0

        fold_result = {
            "fold": fold + 1,
            "mean_score": fold_mean,
            "std_dev": fold_std,
            "metrics": {
                metric: statistics.mean(scores) if scores else 0
                for metric, scores in fold_metrics.items()
            },
        }
        fold_results.append(fold_result)

        # Log fold summary
        logger.log_summary(
            {
                "fold_number": fold + 1,
                "mean_score": fold_mean,
                "std_dev": fold_std,
                "metrics": fold_result["metrics"],
            }
        )

        print(f"   Mean Score: {fold_mean:.3f} ± {fold_std:.3f}")

    # Calculate overall cross-validation metrics
    all_means = [f["mean_score"] for f in fold_results]
    cv_mean = statistics.mean(all_means)
    cv_std = statistics.stdev(all_means) if len(all_means) > 1 else 0

    # Calculate metric stability across folds
    metric_stability = {}
    for metric in ["completeness", "accuracy", "consistency"]:
        metric_values = [f["metrics"][metric] for f in fold_results]
        metric_stability[metric] = {
            "mean": statistics.mean(metric_values),
            "std": statistics.stdev(metric_values) if len(metric_values) > 1 else 0,
        }

    results = {
        "overall_mean": cv_mean,
        "overall_std": cv_std,
        "confidence_interval": (cv_mean - 1.96 * cv_std, cv_mean + 1.96 * cv_std),
        "fold_results": fold_results,
        "metric_stability": metric_stability,
    }

    print("\n📊 Cross-Validation Summary:")
    print(f"   Overall Score: {cv_mean:.3f} ± {cv_std:.3f}")
    print(
        f"   95% CI: [{results['confidence_interval'][0]:.3f}, {results['confidence_interval'][1]:.3f}]"
    )
    print("\n   Metric Stability:")
    for metric, stats in metric_stability.items():
        print(f"     {metric}: {stats['mean']:.3f} ± {stats['std']:.3f}")

    return results


print("\n✅ Cross-validation framework ready!")
# To run: cross_validate_model(model, advanced_dataset, n_folds=3)

# %% [markdown]
# ## 🏭 Example 5: Production Evaluation Pipeline
#
# A complete evaluation pipeline suitable for production deployment.

# %%
print("\n" + "=" * 70)
print("🏭 EXAMPLE 5: Production Evaluation Pipeline")
print("=" * 70)


class ProductionEvaluationPipeline:
    """Complete evaluation pipeline for production use."""

    def __init__(
        self,
        models: List[Model],
        test_dataset: Dataset,
        baseline_model: Optional[Model] = None,
    ):
        self.models = models
        self.test_dataset = test_dataset
        self.baseline_model = baseline_model
        self.results = {}

    @weave.op
    def run_comprehensive_evaluation(self) -> dict:
        """Run full evaluation pipeline."""
        print("\n🏭 Starting Production Evaluation Pipeline")
        print(f"   Models: {[m.__class__.__name__ for m in self.models]}")
        print(f"   Dataset: {self.test_dataset.name}")
        print(
            f"   Baseline: {self.baseline_model.__class__.__name__ if self.baseline_model else 'None'}"
        )

        # Phase 1: Individual model evaluation
        print("\n📊 Phase 1: Individual Model Evaluation")
        for model in self.models:
            print(f"\n   Evaluating {model.__class__.__name__}...")
            self.results[model.__class__.__name__] = self._evaluate_single_model(model)

        # Phase 2: Comparative analysis
        if len(self.models) > 1:
            print("\n📊 Phase 2: Comparative Analysis")
            self.results["comparison"] = self._compare_models()

        # Phase 3: Baseline comparison
        if self.baseline_model:
            print("\n📊 Phase 3: Baseline Comparison")
            self.results["baseline_comparison"] = self._compare_to_baseline()

        # Phase 4: Production readiness check
        print("\n📊 Phase 4: Production Readiness Check")
        self.results["production_readiness"] = self._check_production_readiness()

        # Generate final report
        report = self._generate_report()

        return report

    def _evaluate_single_model(self, model: Model) -> dict:
        """Evaluate a single model comprehensively."""
        # Create evaluation logger
        logger = EvaluationLogger(
            model={
                "name": model.__class__.__name__,
                "evaluation_timestamp": datetime.now().isoformat(),
                "evaluation_type": "production_comprehensive",
            },
            dataset=f"{self.test_dataset.name}_production",
        )

        metrics = {
            "accuracy": [],
            "latency_ms": [],
            "completeness": [],
            "business_value": [],
        }

        for example in self.test_dataset.rows:
            start_time = datetime.now()

            try:
                output = model.predict(example["email"])
                latency = (datetime.now() - start_time).total_seconds() * 1000

                pred_logger = logger.log_prediction(
                    inputs={"email": example["email"]}, output=output.model_dump()
                )

                # Calculate metrics
                accuracy = self._calculate_accuracy(output, example.get("expected", {}))
                completeness = self._calculate_completeness(output)
                business_value = self._calculate_business_value(output)

                metrics["accuracy"].append(accuracy)
                metrics["latency_ms"].append(latency)
                metrics["completeness"].append(completeness)
                metrics["business_value"].append(business_value)

                pred_logger.log_score(scorer="accuracy", score=accuracy)
                pred_logger.log_score(scorer="latency_ms", score=latency)
                pred_logger.log_score(scorer="completeness", score=completeness)
                pred_logger.log_score(scorer="business_value", score=business_value)

                pred_logger.finish()

            except Exception as e:
                print(f"     ❌ Error: {str(e)}")
                metrics["accuracy"].append(0)
                metrics["latency_ms"].append(0)
                metrics["completeness"].append(0)
                metrics["business_value"].append(0)

        # Calculate summary statistics
        summary = {
            metric: {
                "mean": statistics.mean(values) if values else 0,
                "std": statistics.stdev(values) if len(values) > 1 else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
            }
            for metric, values in metrics.items()
        }

        logger.log_summary(summary)

        return summary

    def _calculate_accuracy(self, output, expected):
        """Calculate accuracy score."""
        if not expected:
            return 0.5  # No ground truth

        correct = 0
        total = 0

        for field, expected_value in expected.items():
            if hasattr(output, field):
                actual = getattr(output, field)
                if str(actual).lower() == str(expected_value).lower():
                    correct += 1
                total += 1

        return correct / total if total > 0 else 0

    def _calculate_completeness(self, output):
        """Calculate completeness score."""
        required_fields = ["customer_name", "product", "issue", "severity"]
        score = 0

        for field in required_fields:
            value = getattr(output, field, None)
            if value and value != "Unknown":
                score += 0.25

        return score

    def _calculate_business_value(self, output):
        """Calculate business value score."""
        value = 0

        # Proper severity identification
        if output.severity in ["critical", "high", "medium", "low"]:
            value += 0.3

        # Actionable categorization
        if output.issue_category in ["technical", "billing", "feature_request"]:
            value += 0.3

        # Customer identification
        if output.customer_name and output.customer_name != "Unknown":
            value += 0.2

        # Product identification
        if output.product and any(char.isdigit() for char in output.product):
            value += 0.2

        return value

    def _compare_models(self):
        """Compare all models."""
        comparison = {}

        # Rank models by each metric
        for metric in ["accuracy", "completeness", "business_value"]:
            scores = [
                (name, results[metric]["mean"])
                for name, results in self.results.items()
                if isinstance(results, dict) and metric in results
            ]
            scores.sort(key=lambda x: x[1], reverse=True)
            comparison[f"{metric}_ranking"] = scores

        return comparison

    def _compare_to_baseline(self):
        """Compare models to baseline."""
        if not self.baseline_model:
            return {}

        baseline_results = self._evaluate_single_model(self.baseline_model)

        comparison = {}
        for model_name, results in self.results.items():
            if isinstance(results, dict) and "accuracy" in results:
                comparison[model_name] = {
                    "accuracy_improvement": results["accuracy"]["mean"]
                    - baseline_results["accuracy"]["mean"],
                    "latency_change": results["latency_ms"]["mean"]
                    - baseline_results["latency_ms"]["mean"],
                    "business_value_improvement": results["business_value"]["mean"]
                    - baseline_results["business_value"]["mean"],
                }

        return comparison

    def _check_production_readiness(self):
        """Check if any model meets production criteria."""
        criteria = {
            "min_accuracy": 0.8,
            "max_latency_ms": 1000,
            "min_completeness": 0.9,
            "min_business_value": 0.7,
        }

        readiness = {}

        for model_name, results in self.results.items():
            if isinstance(results, dict) and "accuracy" in results:
                readiness[model_name] = {
                    "accuracy_ok": results["accuracy"]["mean"]
                    >= criteria["min_accuracy"],
                    "latency_ok": results["latency_ms"]["mean"]
                    <= criteria["max_latency_ms"],
                    "completeness_ok": results["completeness"]["mean"]
                    >= criteria["min_completeness"],
                    "business_value_ok": results["business_value"]["mean"]
                    >= criteria["min_business_value"],
                }
                readiness[model_name]["production_ready"] = all(
                    readiness[model_name].values()
                )

        return readiness

    def _generate_report(self):
        """Generate comprehensive evaluation report."""
        report = {
            "evaluation_date": datetime.now().isoformat(),
            "dataset": self.test_dataset.name,
            "models_evaluated": [m.__class__.__name__ for m in self.models],
            "results": self.results,
            "recommendations": [],
        }

        # Add recommendations
        prod_ready = self.results.get("production_readiness", {})
        for model_name, readiness in prod_ready.items():
            if readiness.get("production_ready"):
                report["recommendations"].append(f"✅ {model_name} is production ready")
            else:
                issues = [
                    k.replace("_ok", "")
                    for k, v in readiness.items()
                    if not v and k != "production_ready"
                ]
                report["recommendations"].append(
                    f"❌ {model_name} needs improvement in: {', '.join(issues)}"
                )

        return report


# Create pipeline instance
pipeline = ProductionEvaluationPipeline(
    models=[model, model_b], test_dataset=advanced_dataset, baseline_model=model
)

print("\n✅ Production evaluation pipeline ready!")
print("\n💡 To run the complete pipeline:")
print("   report = pipeline.run_comprehensive_evaluation()")

# %% [markdown]
# ## 🎉 Summary & Best Practices
#
# You've learned advanced evaluation patterns for production use:
#
# ### 🔑 Key Takeaways
#
# 1. **Custom Scorers** - Build domain-specific metrics that matter to your business
# 2. **Multi-Stage Evaluation** - Break complex evaluations into logical stages
# 3. **Statistical Testing** - Use A/B testing with statistical significance
# 4. **Cross-Validation** - Ensure robust evaluation with k-fold validation
# 5. **Production Pipelines** - Comprehensive evaluation before deployment
#
# ### 📋 Best Practices
#
# - **Use Rich Metadata**: Leverage EvaluationLogger's dictionary support for models
# - **Track Everything**: Log intermediate results for debugging
# - **Statistical Rigor**: Don't just compare means - check significance
# - **Business Metrics**: Align evaluation metrics with business outcomes
# - **Automate**: Build pipelines that can run in CI/CD
#
# ### 🚀 Next Steps
#
# 1. Apply these patterns to your own models
# 2. Create custom scorers for your domain
# 3. Build automated evaluation pipelines
# 4. Share your results with your team using Weave's UI
#
# Happy evaluating! 🐝
