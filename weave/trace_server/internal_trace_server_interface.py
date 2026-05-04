"""Internal-only request types used between the external adapter and the
inner trace server implementation.

These subclasses carry rollout/feature-flag fields that must not appear on
the public `trace_server_interface` schemas. The external adapter constructs
them before invoking the inner trace server; inner servers detect them via
`isinstance` and read the extra fields directly.
"""

from pydantic import Field

from weave.trace_server import trace_server_interface as tsi


class InternalCallReadReq(tsi.CallReadReq):
    use_python_cost_hydration: bool = Field(
        default=False,
        description="Internal rollout gate. If true, hydrate call costs in"
        " Python after the call page query instead of in the SQL query.",
    )


class InternalCallsQueryReq(tsi.CallsQueryReq):
    use_python_cost_hydration: bool = Field(
        default=False,
        description="Internal rollout gate. If true, hydrate call costs in"
        " Python after the call page query instead of in the SQL query.",
    )
