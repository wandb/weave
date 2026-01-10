"""
Weave Test Harness - Parametrized tests with scenarios and record mode.

Setup:
    Register this module as a pytest plugin in your conftest.py:

        pytest_plugins = ['weave.trace.weave_test']

    This ensures the session-scoped fixture runs and finalizes evaluation
    loggers at the end of your test session.

Usage:
    from weave.trace.weave_test import weave_test

    # Parent test with inline scenarios (inputs + labels)
    @weave_test(
        op=process_pr,
        inline_scenarios=[
            {"inputs": {"pr_url": "..."}, "labels": {"is_internal": False}},
            {"inputs": {"pr_url": "..."}, "labels": {"is_internal": True}},
        ]
    )
    def test_process_pr(pr_url, output, labels, weave_test_eval):
        if labels.get("is_internal"):
            weave_test_eval.check("no_tweets", len(output.tweets) == 0, "Internal PR")
        else:
            weave_test_eval.check("has_tweets", len(output.tweets) > 0, "...")

    # Child test with derived scenarios (data captured from parent execution)
    # Labels propagate automatically from parent
    @weave_test(op=classify_pr, derive_scenarios_from=[test_process_pr])
    def test_classify_pr(pr_data, output, labels, weave_test_eval):
        if labels.get("is_internal"):
            weave_test_eval.check("internal", not output.is_user_facing, "...")

Check Methods:
    The weave_test_eval object provides several methods for assertions:

    # Simple pass/fail check
    weave_test_eval.check("has_output", output is not None, "Output should exist")

    # Rich check with score, values, and reasoning
    weave_test_eval.check(
        "accuracy",
        accuracy >= 0.9,
        f"Accuracy {accuracy:.1%} below threshold",
        score=accuracy,                           # 0-1 fitness score
        values={"correct": 85, "total": 100},     # supporting metrics
        reasoning="85 out of 100 predictions correct"
    )

    # Numeric range check (auto-calculates score)
    weave_test_eval.check_in_range("word_count", actual=95, low=90, high=110)

    # Closeness check with tolerance
    weave_test_eval.check_close_to("latency", actual=1.2, expected=1.0, rel_tolerance=0.2)

    # Observational metric (doesn't affect pass/fail)
    weave_test_eval.observe("token_count", {"input": 150, "output": 200})

Direct Assertions:
    You can also use standard Python assertions or raise exceptions directly.
    These are captured as test failures and logged to Weave:

    def test_my_op(output, weave_test_eval):
        # Standard assert - will fail the test and log error to Weave
        assert output is not None, "Output should not be None"

        # Raise directly for critical failures
        if output.status == "error":
            raise ValueError(f"Op returned error: {output.message}")

        # Mix with weave_test_eval checks for rich scoring
        weave_test_eval.check("has_data", len(output.data) > 0)

Modes:
    - test (default): Run tests with existing data
    - record-append: Capture new data, append to existing
    - record-overwrite: Capture new data, replace existing

    Set via: WEAVE_TEST_MODE=record-append or pytest --weave-record=append
"""

import asyncio
import atexit
import inspect
import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import weave
from weave import EvaluationLogger
from weave.trace.op import Op, is_op

# Directory where test parameters are stored
WEAVE_TEST_DIR = Path(__file__).parent / ".weave_test"

# Global state
_active_loggers: dict[str, EvaluationLogger] = {}
_test_registry: dict[str, "WeaveTestInfo"] = {}
_captured_calls: dict[str, list[dict[str, Any]]] = {}  # op_name -> list of call data
_current_test_context: dict[str, Any] = {}  # Current test execution context
_cleared_files: set[Path] = set()  # Track files cleared this session (for overwrite mode)
_finalized: bool = False  # Track if loggers have been finalized


# =============================================================================
# Test Registry and Info
# =============================================================================


@dataclass
class Scenario:
    """A test scenario with inputs and labels."""

    inputs: dict[str, Any]
    labels: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        """Create a Scenario from a dict, supporting both formats.

        New format: {"inputs": {...}, "labels": {...}}
        Legacy format: {"pr_url": "..."} -> inputs only, no labels
        """
        if "inputs" in data:
            return cls(
                inputs=data.get("inputs", {}),
                labels=data.get("labels", {}),
            )
        # Legacy format: entire dict is inputs (excluding _lineage)
        inputs = {k: v for k, v in data.items() if not k.startswith("_")}
        labels = data.get("_labels", {})  # Propagated labels from parent
        return cls(inputs=inputs, labels=labels)

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict."""
        return {"inputs": self.inputs, "labels": self.labels}


@dataclass
class WeaveTestInfo:
    """Information about a registered weave test."""

    name: str
    op: Any
    inline_scenarios: list[dict[str, Any]]
    derive_from_tests: list[str]  # Names of parent tests
    project: str | None
    test_fn: Any

    @property
    def dependencies(self) -> list[str]:
        return self.derive_from_tests


def get_derived_file_path(test_name: str, parent_test_name: str) -> Path:
    """Get the file path for derived scenarios from a parent test."""
    test_dir = WEAVE_TEST_DIR / test_name
    return test_dir / f"derived_{parent_test_name}.json"


def load_derived_scenarios(test_name: str, parent_test_name: str) -> list[dict[str, Any]]:
    """Load derived scenarios from file, extracting inputs and labels."""
    file_path = get_derived_file_path(test_name, parent_test_name)
    if not file_path.exists():
        return []
    try:
        with open(file_path) as f:
            data = json.load(f)
        results = []
        for row in data:
            # Extract labels from lineage metadata
            lineage = row.get("_lineage", {})
            labels = lineage.get("labels", {})
            # Strip metadata from inputs
            inputs = {k: v for k, v in row.items() if not k.startswith("_")}
            results.append({"inputs": inputs, "labels": labels})
        return results
    except (json.JSONDecodeError, OSError):
        return []


def save_derived_scenarios(
    test_name: str, parent_test_name: str, scenarios: list[dict[str, Any]], append: bool = False
):
    """Save derived scenarios with lineage metadata.

    In append mode: always append to existing data.
    In overwrite mode: clear file on first write this session, then append.
    """
    file_path = get_derived_file_path(test_name, parent_test_name)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine if we should load existing data
    # - Always load in append mode
    # - In overwrite mode, only load if we've already written to this file this session
    should_load_existing = append or (file_path in _cleared_files)

    existing = []
    if should_load_existing and file_path.exists():
        try:
            with open(file_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Mark file as "cleared" (first write happened) for overwrite mode
    if not append:
        _cleared_files.add(file_path)

    combined = existing + scenarios
    with open(file_path, "w") as f:
        json.dump(combined, f, indent=2, default=str)


def get_test_order() -> list[str]:
    """Get tests in topological order (parents before children)."""
    visited = set()
    order = []

    def visit(name: str):
        if name in visited:
            return
        visited.add(name)
        info = _test_registry.get(name)
        if info:
            for dep in info.dependencies:
                visit(dep)
        order.append(name)

    for name in _test_registry:
        visit(name)

    return order


# =============================================================================
# Call Capture (for record mode)
# =============================================================================


def start_capture(parent_test: str, parent_row_idx: int, parent_labels: dict[str, Any] | None = None):
    """Start capturing child op calls."""
    _current_test_context["parent_test"] = parent_test
    _current_test_context["parent_row_idx"] = parent_row_idx
    _current_test_context["row_id"] = str(uuid.uuid4())[:8]
    _current_test_context["labels"] = parent_labels or {}
    _captured_calls.clear()


def stop_capture() -> dict[str, list[dict[str, Any]]]:
    """Stop capturing and return captured calls."""
    captured = dict(_captured_calls)
    _captured_calls.clear()
    _current_test_context.clear()
    return captured


def _to_plain_dict(obj: Any) -> Any:
    """Convert Weave objects to plain Python types using unwrap."""
    from weave.trace.vals import unwrap

    return unwrap(obj)


def record_call(op_name: str, inputs: dict[str, Any], output: Any, call_id: str | None = None):
    """Record a call to an op (called during execution)."""
    if "parent_test" not in _current_test_context:
        return  # Not in capture mode

    if op_name not in _captured_calls:
        _captured_calls[op_name] = []

    # Convert inputs to plain dicts (handles Weave objects and dataclasses)
    try:
        plain_inputs = _to_plain_dict(inputs)
    except Exception as e:
        plain_inputs = {"_error": str(e)}
    _captured_calls[op_name].append(
        {
            "_lineage": {
                "parent_test": _current_test_context["parent_test"],
                "parent_row_idx": _current_test_context["parent_row_idx"],
                "row_id": _current_test_context["row_id"],
                "weave_call_id": call_id,
                "captured_at": datetime.now(UTC).isoformat(),
                "labels": _current_test_context.get("labels", {}),  # Propagate labels
            },
            **plain_inputs,
        }
    )


def _capture_child_calls(parent_call: Any):
    """Capture child op calls from a Weave call object."""
    if "parent_test" not in _current_test_context:
        return

    children = []
    if hasattr(parent_call, "children"):
        try:
            children = list(parent_call.children())
        except Exception:
            pass

    for child in children:
        try:
            op_name = None
            if hasattr(child, "op_name"):
                op_name = child.op_name
            elif hasattr(child, "_op_name"):
                op_name = child._op_name

            if not op_name:
                continue

            inputs = {}
            if hasattr(child, "inputs"):
                inputs = dict(child.inputs) if child.inputs else {}

            call_id = getattr(child, "id", None)
            record_call(op_name, inputs, None, call_id)

            _capture_child_calls(child)
        except Exception:
            continue


# =============================================================================
# WeaveTestEval (scorer helper)
# =============================================================================


@dataclass
class CheckResult:
    """Result of a check with optional rich metadata.

    Args:
        passed: Whether the check passed (required).
        score: Optional fitness score from 0.0 to 1.0.
        values: Optional supporting values/metrics used in the check.
        reasoning: Optional human-readable explanation.
    """

    passed: bool
    score: float | None = None
    values: Any = None
    reasoning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for logging, excluding None values."""
        result: dict[str, Any] = {"passed": self.passed}
        if self.score is not None:
            result["score"] = self.score
        if self.values is not None:
            result["values"] = self.values
        if self.reasoning is not None:
            result["reasoning"] = self.reasoning
        return result


class WeaveTestEval:
    """Utility class for logging scored assertions in weave tests.

    Provides methods for checking conditions and logging rich evaluation data
    that integrates with Weave's evaluation system.

    Examples:
        # Simple pass/fail check
        weave_test_eval.check("has_output", output is not None)

        # Check with error description (for pytest output)
        weave_test_eval.check("valid_length", len(text) > 0, "Text should not be empty")

        # Rich check with score and supporting values
        weave_test_eval.check(
            "word_count_accuracy",
            abs(actual - expected) <= tolerance,
            score=(expected - abs(actual - expected)) / expected,
            values={"actual": actual, "expected": expected, "tolerance": tolerance},
            reasoning=f"Word count {actual} is within {tolerance} of target {expected}"
        )

        # Observational metric (doesn't affect pass/fail)
        weave_test_eval.observe("latency_ms", response_time * 1000)
        weave_test_eval.observe("token_count", {"input": 150, "output": 200})
    """

    def __init__(self, pred_logger: Any):
        self._pred_logger = pred_logger
        self._failures: list[tuple[str, str]] = []

    def check(
        self,
        label: str,
        passed: bool,
        error_description: str = "",
        *,
        score: float | None = None,
        values: Any = None,
        reasoning: str | None = None,
    ) -> bool:
        """Log a scored assertion. Does NOT raise immediately.

        Args:
            label: Name for this check (used as scorer name in Weave).
            passed: Whether the check passed.
            error_description: Message shown in pytest output on failure.
            score: Optional fitness score from 0.0 to 1.0.
            values: Optional supporting values/metrics (any JSON-serializable data).
            reasoning: Optional human-readable explanation of the result.

        Returns:
            bool: The passed value (for chaining or conditional logic).

        Examples:
            # Simple check
            weave_test_eval.check("is_valid", result.is_valid, "Result should be valid")

            # Rich check with all metadata
            accuracy = correct / total
            weave_test_eval.check(
                "accuracy",
                accuracy >= 0.9,
                f"Accuracy {accuracy:.1%} below 90% threshold",
                score=accuracy,
                values={"correct": correct, "total": total},
                reasoning=f"Got {correct}/{total} correct"
            )
        """
        # Build score data - use dict if we have rich metadata, else just passed
        if score is not None or values is not None or reasoning is not None:
            result = CheckResult(
                passed=passed,
                score=score,
                values=values,
                reasoning=reasoning,
            )
            score_data: bool | dict[str, Any] = result.to_dict()
        else:
            score_data = passed

        self._pred_logger.log_score(scorer=label, score=score_data)

        if not passed:
            # Use reasoning as error description if not provided
            desc = error_description or reasoning or ""
            self._failures.append((label, desc))

        return passed

    def observe(
        self,
        label: str,
        value: float | bool | dict[str, Any],
        *,
        reasoning: str | None = None,
    ) -> None:
        """Log an observational metric that doesn't affect pass/fail.

        Use this for metrics you want to track but that shouldn't cause
        test failures (e.g., latency, token counts, intermediate scores).

        Args:
            label: Name for this metric (used as scorer name in Weave).
            value: The metric value (float, bool, or dict).
            reasoning: Optional explanation of what this metric represents.

        Examples:
            # Simple numeric observation
            weave_test_eval.observe("latency_ms", response_time * 1000)

            # Structured observation
            weave_test_eval.observe("token_usage", {
                "input_tokens": 150,
                "output_tokens": 200,
                "total_cost": 0.003
            })

            # With reasoning
            weave_test_eval.observe(
                "confidence",
                model_confidence,
                reasoning="Model's self-reported confidence score"
            )
        """
        if reasoning is not None and isinstance(value, dict):
            value = {**value, "reasoning": reasoning}
        elif reasoning is not None:
            value = {"value": value, "reasoning": reasoning}

        self._pred_logger.log_score(scorer=label, score=value)

    def check_in_range(
        self,
        label: str,
        actual: float,
        low: float,
        high: float,
        *,
        reasoning: str | None = None,
    ) -> bool:
        """Check if a value falls within a range [low, high].

        Automatically calculates a score based on how centered the value is
        within the range, and logs the actual/expected values.

        Args:
            label: Name for this check.
            actual: The actual value to check.
            low: Lower bound (inclusive).
            high: Upper bound (inclusive).
            reasoning: Optional additional explanation.

        Returns:
            bool: True if actual is within [low, high].

        Examples:
            # Check word count is within 10% of target
            target = 100
            weave_test_eval.check_in_range(
                "word_count",
                actual=len(text.split()),
                low=target * 0.9,
                high=target * 1.1,
            )
        """
        passed = low <= actual <= high

        # Calculate score: 1.0 at midpoint, 0.0 at boundaries or outside
        midpoint = (low + high) / 2
        half_range = (high - low) / 2
        if half_range > 0:
            distance_from_mid = abs(actual - midpoint)
            score = max(0.0, 1.0 - (distance_from_mid / half_range))
        else:
            score = 1.0 if actual == midpoint else 0.0

        default_reasoning = f"Value {actual} {'is' if passed else 'is NOT'} in range [{low}, {high}]"

        return self.check(
            label,
            passed,
            default_reasoning,
            score=score,
            values={"actual": actual, "low": low, "high": high},
            reasoning=reasoning or default_reasoning,
        )

    def check_close_to(
        self,
        label: str,
        actual: float,
        expected: float,
        tolerance: float | None = None,
        rel_tolerance: float | None = None,
        *,
        reasoning: str | None = None,
    ) -> bool:
        """Check if a value is close to an expected value.

        Args:
            label: Name for this check.
            actual: The actual value to check.
            expected: The expected value.
            tolerance: Absolute tolerance (if provided).
            rel_tolerance: Relative tolerance as fraction (e.g., 0.1 for 10%).
                          If both tolerances provided, uses the larger range.

        Returns:
            bool: True if actual is within tolerance of expected.

        Examples:
            # Within 5 units
            weave_test_eval.check_close_to("score", actual=95, expected=100, tolerance=5)

            # Within 10% of expected
            weave_test_eval.check_close_to("count", actual=95, expected=100, rel_tolerance=0.1)
        """
        # Calculate effective tolerance range
        abs_tol = tolerance if tolerance is not None else 0
        rel_tol_value = abs(expected * rel_tolerance) if rel_tolerance is not None else 0
        effective_tol = max(abs_tol, rel_tol_value)

        if effective_tol == 0:
            raise ValueError("Must provide tolerance or rel_tolerance")

        diff = abs(actual - expected)
        passed = diff <= effective_tol

        # Score based on how close we are (1.0 = exact match, 0.0 = at tolerance boundary)
        score = max(0.0, 1.0 - (diff / effective_tol)) if effective_tol > 0 else (1.0 if diff == 0 else 0.0)

        default_reasoning = f"Value {actual} {'is' if passed else 'is NOT'} within {effective_tol} of {expected} (diff={diff})"

        return self.check(
            label,
            passed,
            default_reasoning,
            score=score,
            values={"actual": actual, "expected": expected, "diff": diff, "tolerance": effective_tol},
            reasoning=reasoning or default_reasoning,
        )

    def has_failures(self) -> bool:
        """Check if any checks have failed."""
        return len(self._failures) > 0

    def raise_if_failed(self) -> None:
        """Raise AssertionError if any checks failed."""
        if self._failures:
            messages = [f"  - {label}: {desc}" for label, desc in self._failures]
            raise AssertionError(f"{len(self._failures)} check(s) failed:\n" + "\n".join(messages))


# =============================================================================
# Mode Detection
# =============================================================================


def get_mode() -> str:
    """Get current test mode: 'test', 'record-append', or 'record-overwrite'."""
    return os.environ.get("WEAVE_TEST_MODE", "test")


def is_record_mode() -> bool:
    return get_mode().startswith("record")


def is_append_mode() -> bool:
    return get_mode() == "record-append"


# =============================================================================
# Logger Management
# =============================================================================


def _get_or_create_logger(test_name: str, project: str | None) -> EvaluationLogger:
    if test_name not in _active_loggers:
        if project:
            weave.init(project)
        _active_loggers[test_name] = EvaluationLogger(
            name=test_name,
            model=test_name,
            dataset=f".weave_test/{test_name}",
        )
    return _active_loggers[test_name]


# =============================================================================
# Main Decorator
# =============================================================================


def weave_test(
    func=None,
    *,
    op: Any = None,
    inline_scenarios: list[dict[str, Any]] | None = None,
    derive_scenarios_from: list[Callable] | None = None,
    project: str | None = None,
):
    """Decorator that creates a parametrized pytest test with Weave evaluation logging.

    This decorator transforms a test function into a parametrized pytest test that:
    1. Runs your weave.op with each scenario's inputs
    2. Passes the output to your test function for validation
    3. Logs all results to Weave as an evaluation for analysis and comparison

    Args:
        op: A @weave.op decorated function to test. The op is called with each
            scenario's inputs, and the output is passed to your test function.
            If None, no op is called and only inputs are passed to the test.
        inline_scenarios: List of test scenarios defined inline. Each scenario
            should be a dict with "inputs" (required) and "labels" (optional):
            [
                {"inputs": {"x": 1, "y": 2}, "labels": {"expected_sum": 3}},
                {"inputs": {"x": 10, "y": 20}, "labels": {"expected_sum": 30}},
            ]
        derive_scenarios_from: List of parent test functions to derive scenarios
            from. In record mode, child op calls are captured and saved as
            scenarios for tests that derive from the parent.
        project: Weave project name for logging (e.g., "entity/project").
            If provided, weave.init() is called with this project.

    Test Function Parameters:
        Your test function can request any of these parameters by name:

        - **Input parameters**: Any key from your scenario inputs (e.g., `x`, `y`)
        - **output**: The return value from calling the op (requires `op` to be set)
        - **labels**: Dict of labels from the scenario for conditional assertions
        - **weave_test_eval**: A WeaveTestEval instance for logging scored checks

    Assertion Methods:
        You can use multiple assertion styles in your test:

        1. **weave_test_eval.check()** - Logged checks that don't immediately fail:
           ```python
           weave_test_eval.check("valid", output.is_valid, "Should be valid")
           ```

        2. **Standard assertions** - Immediate failures, logged to Weave:
           ```python
           assert output is not None, "Output required"
           ```

        3. **Raise exceptions** - For critical failures:
           ```python
           if output.error:
               raise ValueError(f"Op failed: {output.error}")
           ```

    Examples:
        Basic test with inline scenarios:

        ```python
        @weave_test(
            op=my_classifier,
            project="my-team/my-project",
            inline_scenarios=[
                {"inputs": {"text": "I love this!"}, "labels": {"sentiment": "positive"}},
                {"inputs": {"text": "This is terrible"}, "labels": {"sentiment": "negative"}},
            ]
        )
        def test_classifier(text, output, labels, weave_test_eval):
            # Rich check with score
            weave_test_eval.check(
                "correct_sentiment",
                output.sentiment == labels["sentiment"],
                score=output.confidence,
                values={"predicted": output.sentiment, "expected": labels["sentiment"]},
            )
        ```

        Test without weave_test_eval (just use assertions):

        ```python
        @weave_test(
            op=my_op,
            inline_scenarios=[{"inputs": {"x": 1}}]
        )
        def test_simple(x, output):
            assert output > 0, "Output must be positive"
            assert isinstance(output, int), "Output must be int"
        ```
    """

    def decorator(fn):
        test_name = fn.__name__

        # Validate op
        if op is not None and not is_op(op):
            raise TypeError(
                f"op must be a weave.op decorated function, got {type(op).__name__}. "
                "Wrap your function with @weave.op"
            )

        # Get parent test names from derive_scenarios_from
        derive_from_tests = []
        if derive_scenarios_from:
            for parent_test in derive_scenarios_from:
                # Get the original test name (before pytest decoration)
                parent_name = getattr(parent_test, "__name__", None)
                if parent_name:
                    derive_from_tests.append(parent_name)

        # Register test
        test_info = WeaveTestInfo(
            name=test_name,
            op=op,
            inline_scenarios=inline_scenarios or [],
            derive_from_tests=derive_from_tests,
            project=project,
            test_fn=fn,
        )
        _test_registry[test_name] = test_info

        # Check function signature
        sig = inspect.signature(fn)
        wants_eval = "weave_test_eval" in sig.parameters
        wants_output = "output" in sig.parameters
        wants_labels = "labels" in sig.parameters

        # Collect and normalize all scenarios
        all_scenarios: list[Scenario] = []

        # Add inline scenarios (normalize to Scenario)
        if inline_scenarios:
            for s in inline_scenarios:
                all_scenarios.append(Scenario.from_dict(s))

        # Add derived scenarios from parent tests (already in new format)
        for parent_name in derive_from_tests:
            derived = load_derived_scenarios(test_name, parent_name)
            for s in derived:
                all_scenarios.append(Scenario.from_dict(s))

        if not all_scenarios:

            @pytest.mark.skip(reason=f"No scenarios for {test_name}")
            def skipped(*args, **kwargs):
                pass

            skipped.__name__ = fn.__name__
            return skipped

        # Extract parameter names from inputs of first scenario
        param_names = list(all_scenarios[0].inputs.keys())

        # Check if op is async
        is_async_op = False
        if op is not None and isinstance(op, Op):
            # Check if the underlying function is async
            is_async_op = asyncio.iscoroutinefunction(op.resolve_fn)

        # Check if test function is async
        is_async_test = asyncio.iscoroutinefunction(fn)

        # If either op or test is async, we need an async wrapper
        needs_async = is_async_op or is_async_test

        # Build dynamic wrapper with _scenario_idx for labels lookup
        param_str = ", ".join(param_names)
        if needs_async:
            wrapper_code = f"""
async def wrapper({param_str}, _scenario_idx):
    inputs = {{{", ".join(f'"{n}": {n}' for n in param_names)}}}
    await _run_test(inputs, _scenario_idx)
"""
        else:
            wrapper_code = f"""
def wrapper({param_str}, _scenario_idx):
    inputs = {{{", ".join(f'"{n}": {n}' for n in param_names)}}}
    _run_test(inputs, _scenario_idx)
"""

        def make_runner(scenarios: list[Scenario], is_async: bool):
            if is_async:
                async def _run_test_async(inputs: dict, scenario_idx: int):
                    scenario = scenarios[scenario_idx]
                    labels = scenario.labels
                    eval_logger = _get_or_create_logger(test_name, project)

                    # Start capture if in record mode (pass labels for propagation)
                    if is_record_mode():
                        start_capture(test_name, scenario_idx, labels)

                    # Call op if provided
                    output = None
                    call_id = None
                    if op is not None:
                        if is_async_op:
                            output, call = await op.call(**inputs)
                        else:
                            output, call = op.call(**inputs)
                        call_id = getattr(call, "id", None)

                        if is_record_mode() and call_id:
                            _capture_child_calls(call)

                    # Stop capture and save derived data
                    if is_record_mode():
                        captured = stop_capture()
                        # Save captured calls to child tests' derived sources
                        for child_name, child_info in _test_registry.items():
                            if child_name == test_name:
                                continue
                            if test_name in child_info.derive_from_tests:
                                # Find calls to the child's op
                                if child_info.op is not None:
                                    target_op_name = getattr(child_info.op, "name", None)
                                    # Match captured op URIs that contain the target op name
                                    # URIs look like: weave:///.../op/classify_pr:hash
                                    for captured_uri, calls in captured.items():
                                        if f"/op/{target_op_name}:" in captured_uri:
                                            save_derived_scenarios(
                                                child_name,
                                                test_name,
                                                calls,
                                                append=is_append_mode(),
                                            )
                                            break

                    pred_logger = eval_logger.log_prediction(inputs=inputs, output=output)
                    eval_helper = WeaveTestEval(pred_logger) if wants_eval else None

                    passed = False
                    error_msg = None
                    try:
                        test_kwargs = dict(inputs)
                        if wants_output:
                            test_kwargs["output"] = output
                        if wants_labels:
                            test_kwargs["labels"] = labels
                        if wants_eval:
                            test_kwargs["weave_test_eval"] = eval_helper

                        if is_async_test:
                            await fn(**test_kwargs)
                        else:
                            fn(**test_kwargs)

                        if eval_helper:
                            eval_helper.raise_if_failed()

                        passed = True
                    except AssertionError as e:
                        error_msg = str(e)
                        raise
                    except Exception as e:
                        error_msg = str(e)
                        raise
                    finally:
                        has_check_failures = eval_helper.has_failures() if eval_helper else False
                        pred_logger.log_score(scorer="result", score={
                            "passed": passed and not has_check_failures,
                            "error": error_msg,
                        })
                        pred_logger.finish()

                return _run_test_async
            else:
                def _run_test_sync(inputs: dict, scenario_idx: int):
                    scenario = scenarios[scenario_idx]
                    labels = scenario.labels
                    eval_logger = _get_or_create_logger(test_name, project)

                    # Start capture if in record mode (pass labels for propagation)
                    if is_record_mode():
                        start_capture(test_name, scenario_idx, labels)

                    # Call op if provided
                    output = None
                    call_id = None
                    if op is not None:
                        output, call = op.call(**inputs)
                        call_id = getattr(call, "id", None)

                        if is_record_mode() and call_id:
                            _capture_child_calls(call)

                    # Stop capture and save derived data
                    if is_record_mode():
                        captured = stop_capture()
                        # Save captured calls to child tests' derived sources
                        for child_name, child_info in _test_registry.items():
                            if child_name == test_name:
                                continue
                            if test_name in child_info.derive_from_tests:
                                # Find calls to the child's op
                                if child_info.op is not None:
                                    target_op_name = getattr(child_info.op, "name", None)
                                    # Match captured op URIs that contain the target op name
                                    # URIs look like: weave:///.../op/classify_pr:hash
                                    for captured_uri, calls in captured.items():
                                        if f"/op/{target_op_name}:" in captured_uri:
                                            save_derived_scenarios(
                                                child_name,
                                                test_name,
                                                calls,
                                                append=is_append_mode(),
                                            )
                                            break

                    pred_logger = eval_logger.log_prediction(inputs=inputs, output=output)
                    eval_helper = WeaveTestEval(pred_logger) if wants_eval else None

                    passed = False
                    error_msg = None
                    try:
                        test_kwargs = dict(inputs)
                        if wants_output:
                            test_kwargs["output"] = output
                        if wants_labels:
                            test_kwargs["labels"] = labels
                        if wants_eval:
                            test_kwargs["weave_test_eval"] = eval_helper

                        fn(**test_kwargs)

                        if eval_helper:
                            eval_helper.raise_if_failed()

                        passed = True
                    except AssertionError as e:
                        error_msg = str(e)
                        raise
                    except Exception as e:
                        error_msg = str(e)
                        raise
                    finally:
                        has_check_failures = eval_helper.has_failures() if eval_helper else False
                        pred_logger.log_score(scorer="result", score={
                            "passed": passed and not has_check_failures,
                            "error": error_msg,
                        })
                        pred_logger.finish()

                return _run_test_sync

        _run_test = make_runner(all_scenarios, needs_async)
        local_ns: dict[str, Any] = {"_run_test": _run_test}
        exec(wrapper_code, local_ns)  # noqa: S102
        wrapper = local_ns["wrapper"]
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__

        # Build parametrize values (include _scenario_idx for labels lookup)
        extended_param_names = param_names + ["_scenario_idx"]
        param_values = [
            tuple(s.inputs.get(name) for name in param_names) + (idx,)
            for idx, s in enumerate(all_scenarios)
        ]

        def make_id(s: Scenario) -> str | None:
            for v in s.inputs.values():
                if isinstance(v, str) and len(v) < 50:
                    return v
            return None

        ids = [make_id(s) for s in all_scenarios]

        # Apply parametrize and usefixtures for session finalization
        decorated = pytest.mark.usefixtures("weave_test_session")(
            pytest.mark.parametrize(extended_param_names, param_values, ids=ids)(wrapper)
        )

        # Add asyncio marker for async tests
        if needs_async:
            decorated = pytest.mark.asyncio(decorated)

        return decorated

    if func is not None:
        return decorator(func)
    return decorator


# =============================================================================
# Pytest Hooks and Fixtures
# =============================================================================


def pytest_addoption(parser):
    """Add --weave-record option."""
    parser.addoption(
        "--weave-record",
        action="store",
        default=None,
        choices=["append", "overwrite"],
        help="Record mode: append or overwrite",
    )


def pytest_configure(config):
    """Set mode from command line option and reset session state."""
    global _finalized
    _finalized = False  # Reset for new test session

    record = config.getoption("--weave-record", None)
    if record:
        os.environ["WEAVE_TEST_MODE"] = f"record-{record}"


def _finalize_loggers():
    """Finalize all active evaluation loggers.

    This is idempotent - calling multiple times is safe.
    Called by the weave_test_session fixture at session end,
    pytest_sessionfinish hook, and atexit handler as fallbacks.
    """
    global _finalized
    if _finalized:
        return
    _finalized = True

    for name, logger in list(_active_loggers.items()):
        try:
            logger.log_summary()
        except Exception as e:
            print(f"Warning: Failed to log summary for {name}: {e}")
    _active_loggers.clear()


@pytest.fixture(scope="session")
def weave_test_session():
    """Session-scoped fixture that finalizes loggers at session end.

    This fixture is automatically used by all @weave_test decorated tests.
    To ensure it's available, register this module as a pytest plugin in conftest.py:

        pytest_plugins = ['weave.trace.weave_test']

    Returns:
        None: This fixture only provides session cleanup via finalization.

    Examples:
        # In conftest.py:
        pytest_plugins = ['weave.trace.weave_test']

        # Tests decorated with @weave_test will automatically use this fixture.
    """
    yield
    _finalize_loggers()


# Register atexit handler as fallback for when pytest hooks aren't registered.
# This ensures log_summary is called even if the module isn't registered as a pytest plugin.
atexit.register(_finalize_loggers)


def pytest_sessionfinish(session, exitstatus):
    """Finalize evaluations at pytest session end.

    Note: This hook is only called if this module is registered as a pytest plugin.
    To register, add to conftest.py: pytest_plugins = ['weave.trace.weave_test']
    The atexit handler provides a fallback if not registered.
    """
    _finalize_loggers()
