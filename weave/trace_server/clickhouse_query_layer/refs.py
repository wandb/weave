# ClickHouse Refs - Ref resolution operations

from typing import Any, cast

from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi

# Type alias for object ref list
ObjRefListType = list[ri.InternalObjectRef]


class RefsRepository:
    """Repository for ref resolution operations.

    This class provides a thin wrapper around ref resolution functionality.
    The actual resolution logic is complex and relies on multiple helpers
    from refs_internal_server_util.
    """

    def __init__(
        self,
        parsed_refs_read_batch_func: "callable[[ObjRefListType, dict[str, Any] | None], list[Any]]",
    ):
        """Initialize the refs repository.

        Args:
            parsed_refs_read_batch_func: Function to read parsed refs in batch.
        """
        self._parsed_refs_read_batch = parsed_refs_read_batch_func

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        """Read multiple refs in batch.

        Args:
            req: Request containing refs to read.

        Returns:
            Response with resolved values.

        Raises:
            ValueError: If too many refs, or if table/call refs are provided.
        """
        if len(req.refs) > 1000:
            raise ValueError("Too many refs")

        # First, parse the refs
        parsed_raw_refs = [ri.parse_internal_uri(r) for r in req.refs]

        # Business logic to ensure that we don't have raw TableRefs (not allowed)
        if any(isinstance(r, ri.InternalTableRef) for r in parsed_raw_refs):
            raise ValueError("Table refs not supported")

        # Business logic to ensure that we don't have raw CallRefs (not allowed)
        if any(isinstance(r, ri.InternalCallRef) for r in parsed_raw_refs):
            raise ValueError(
                "Call refs not supported in batch read, use calls_query_stream"
            )

        parsed_refs = cast(ObjRefListType, parsed_raw_refs)
        vals = self._parsed_refs_read_batch(parsed_refs, None)

        return tsi.RefsReadBatchRes(vals=vals)
