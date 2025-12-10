"""
Weave Test Harness - Parametrized tests with scenarios and record mode.

Usage:
    from weave_pytest_harness import weave_test

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

Modes:
    - test (default): Run tests with existing data
    - record-append: Capture new data, append to existing
    - record-overwrite: Capture new data, replace existing

    Set via: WEAVE_TEST_MODE=record-append or pytest --weave-record=append
"""

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
from weave.trace.op import is_op

# Directory where test parameters are stored
WEAVE_TEST_DIR = Path(__file__).parent / ".weave_test"

# Global state
_active_loggers: dict[str, EvaluationLogger] = {}
_test_registry: dict[str, "WeaveTestInfo"] = {}
_captured_calls: dict[str, list[dict[str, Any]]] = {}  # op_name -> list of call data
_current_test_context: dict[str, Any] = {}  # Current test execution context
_cleared_files: set[Path] = set()  # Track files cleared this session (for overwrite mode)


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


class WeaveTestEval:
    """Utility class for logging scored assertions."""

    def __init__(self, pred_logger: Any):
        self._pred_logger = pred_logger
        self._failures: list[tuple[str, str]] = []

    def check(self, label: str, condition: bool, error_description: str = "") -> bool:
        """Log a scored assertion. Does NOT raise immediately."""
        self._pred_logger.log_score(scorer=label, score=condition)
        if not condition:
            self._failures.append((label, error_description))
        return condition

    def has_failures(self) -> bool:
        return len(self._failures) > 0

    def raise_if_failed(self) -> None:
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
    """
    Decorator that creates a parametrized test with Weave evaluation logging.

    Args:
        op: The weave.op to test. Called with inputs, output passed to test.
        inline_scenarios: List of test scenarios defined inline.
        derive_scenarios_from: List of parent test functions to derive scenarios from.
        project: Weave project name for logging.
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

        # Build dynamic wrapper with _scenario_idx for labels lookup
        param_str = ", ".join(param_names)
        wrapper_code = f"""
def wrapper({param_str}, _scenario_idx):
    inputs = {{{", ".join(f'"{n}": {n}' for n in param_names)}}}
    _run_test(inputs, _scenario_idx)
"""

        def make_runner(scenarios: list[Scenario]):
            def _run_test(inputs: dict, scenario_idx: int):
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
                    pred_logger.log_score(scorer="passed", score=passed)
                    if error_msg:
                        pred_logger.log_score(scorer="error", score=error_msg)
                    pred_logger.finish()

            return _run_test

        _run_test = make_runner(all_scenarios)
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

        decorated = pytest.mark.parametrize(extended_param_names, param_values, ids=ids)(wrapper)
        return decorated

    if func is not None:
        return decorator(func)
    return decorator


# =============================================================================
# Pytest Hooks
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
    """Set mode from command line option."""
    record = config.getoption("--weave-record", None)
    if record:
        os.environ["WEAVE_TEST_MODE"] = f"record-{record}"


def pytest_sessionfinish(session, exitstatus):
    """Finalize evaluations."""
    for name, logger in _active_loggers.items():
        try:
            logger.log_summary()
        except Exception as e:
            print(f"Warning: Failed to log summary for {name}: {e}")
    _active_loggers.clear()
