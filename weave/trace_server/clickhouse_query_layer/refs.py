# ClickHouse Refs - Ref resolution operations

from collections.abc import Callable
from typing import Any, Protocol, cast

from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError, ObjectDeletedError

# Type alias for object ref list
ObjRefListType = list[ri.InternalObjectRef]


class TableRowReadResult(Protocol):
    """Protocol for table row read result."""

    val: Any


class RefsRepository:
    """Repository for ref resolution operations.

    This class provides ref resolution functionality including:
    - Batch ref reading
    - Object ref path traversal (key, attr, index, id operations)
    """

    def __init__(
        self,
        obj_read_func: Callable[[tsi.ObjReadReq], tsi.ObjReadRes],
        table_row_read_func: Callable[[str, str], TableRowReadResult],
    ):
        """Initialize the refs repository.

        Args:
            obj_read_func: Function to read object by request.
            table_row_read_func: Function to read table row by project_id and row_digest.
        """
        self._obj_read = obj_read_func
        self._table_row_read = table_row_read_func

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
        vals = self.parsed_refs_read_batch(parsed_refs, None)

        return tsi.RefsReadBatchRes(vals=vals)

    def parsed_refs_read_batch(
        self,
        refs: list[ri.InternalObjectRef],
        cache: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Read parsed refs in batch.

        This is the core ref resolution logic that handles object refs.
        The `extra` path is processed in pairs: (operation_type, argument).
        - "key" (DICT_KEY_EDGE_NAME): dict key lookup
        - "attr" (OBJECT_ATTR_EDGE_NAME): attribute/dict key lookup
        - "index" (LIST_INDEX_EDGE_NAME): list index lookup
        - "id" (TABLE_ROW_ID_EDGE_NAME): table row ID lookup

        Args:
            refs: List of parsed internal object refs to read.
            cache: Optional cache dict for storing resolved values.

        Returns:
            List of resolved values, with None for refs that couldn't be resolved.
        """
        if not refs:
            return []

        results = []
        cache = cache or {}

        for ref in refs:
            # Check cache first
            cache_key = ref.uri()
            if cache_key in cache:
                results.append(cache[cache_key])
                continue

            # Read the object
            try:
                obj_req = tsi.ObjReadReq(
                    project_id=ref.project_id,
                    object_id=ref.name,
                    digest=ref.version,
                )
                obj_res = self._obj_read(obj_req)
                val = obj_res.obj.val

                # Handle extra path if present (processed in pairs)
                extra = ref.extra
                for extra_index in range(0, len(extra), 2):
                    if extra_index + 1 >= len(extra):
                        break
                    op, arg = extra[extra_index], extra[extra_index + 1]

                    if op == ri.DICT_KEY_EDGE_NAME:
                        # Dict key lookup
                        val = val[arg]
                    elif op == ri.OBJECT_ATTR_EDGE_NAME:
                        # Attribute/dict key lookup
                        val = val[arg]
                    elif op == ri.LIST_INDEX_EDGE_NAME:
                        # List index lookup
                        val = val[int(arg)]
                    elif op == ri.TABLE_ROW_ID_EDGE_NAME:
                        # Table row ID lookup
                        weave_internal_prefix = ri.WEAVE_INTERNAL_SCHEME + ":///"
                        if isinstance(val, str) and val.startswith(
                            weave_internal_prefix
                        ):
                            table_ref = ri.parse_internal_uri(val)
                            if not isinstance(table_ref, ri.InternalTableRef):
                                raise ValueError(
                                    "invalid data layout encountered, expected TableRef when resolving id"
                                )
                            row = self._table_row_read(
                                table_ref.project_id,
                                arg,
                            )
                            val = row.val
                        else:
                            raise ValueError(
                                "invalid data layout encountered, expected TableRef when resolving id"
                            )
                    else:
                        raise ValueError(f"Unknown ref type: {op}")

                cache[cache_key] = val
                results.append(val)
            except (
                NotFoundError,
                ObjectDeletedError,
                KeyError,
                IndexError,
                ValueError,
            ):
                results.append(None)

        return results
