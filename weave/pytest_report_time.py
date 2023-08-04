from _pytest.config import Config
from _pytest.reports import TestReport
from typing import Tuple, Optional


def pytest_report_teststatus(
    report: TestReport, config: Config
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if report.when == "call":
        duration = "{:.2f}s".format(report.duration)
        if report.failed:
            return "failed", f"F", f"FAILED({duration})"
        elif report.skipped:
            return "skipped", f"S", f"SKIPPED({duration})"
        elif report.passed:
            return "passed", f".", f"PASSED({duration})"
        else:
            return "unknown", f"?", "UNKNOWN({duration})"

    return None, None, None
