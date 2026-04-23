from __future__ import annotations

from datetime import datetime

from weave.flow.util import make_memorable_name
from weave.trace.call import Call


def default_evaluation_display_name(call: Call) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"eval-{date}-{unique_name}"
