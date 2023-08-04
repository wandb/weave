from _pytest.config import Config
from _pytest.reports import TestReport
from typing import Tuple, Optional


def pytest_report_teststatus(
    report: TestReport, config: Config
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if report.when == "call":
        duration = "{:.2f}s".format(report.duration)
        if report.failed:
            return "failed", "F", f"FAILED({duration})"
        elif report.passed:
            return "passed", ".", f"PASSED({duration})"
        elif hasattr(
            report, "wasxfail"
        ):  # 'xfail' means that the test was expected to fail
            return report.outcome, "x", "XFAIL"
        elif report.skipped:
            return report.outcome, "s", "SKIPPED"

    elif report.when in ("setup", "teardown"):
        if report.failed:
            return "error", "E", "ERROR"

    return None, None, None
