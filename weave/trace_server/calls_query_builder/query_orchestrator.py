"""Query orchestrators for building calls queries.

Orchestrators manage the entire query building process:
1. Collect all CTEs in proper order
2. Build main query using shared components
3. Handle special features (costs, object refs)
4. Render final SQL
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, Optional, cast

from weave.trace_server import trace_server_interface as tsi

if TYPE_CHECKING:
    from weave.trace_server.calls_query_builder.calls_query_builder import CallsQuery
from weave.trace_server.calls_query_builder.cte_registry import CTERegistry
from weave.trace_server.calls_query_builder.object_ref_query_builder import (
    build_object_ref_ctes,
    get_all_object_ref_conditions,
    is_object_ref_operand,
)
from weave.trace_server.calls_query_builder.query_components import (
    build_filter_conditions,
    build_limit_offset_clause,
    build_order_by_clause,
    build_query_joins,
)
from weave.trace_server.calls_query_builder.utils import (
    param_slot,
    safely_format_sql,
)
from weave.trace_server.orm import ParamBuilder, combine_conditions
from weave.trace_server.token_costs import cost_query

logger = logging.getLogger(__name__)


class BaseQueryOrchestrator(ABC):
    """Base orchestrator for building calls queries.

    Orchestrators manage the entire query building process in phases:
    1. Object reference CTEs (if needed)
    2. Table-specific CTEs (optimization or include_running)
    3. Main query (using shared components)
    4. Cost CTEs (if needed)
    5. Render final SQL

    Subclasses implement table-specific logic.
    """

    def __init__(
        self,
        query: "CallsQuery",  # type: ignore
        pb: ParamBuilder,
    ):
        self.query = query
        self.pb = pb
        self.cte_registry = CTERegistry()
        self.project_id_param_slot = param_slot(
            pb.add_param(query.project_id), "String"
        )
        self._field_to_object_join_alias_map: Optional[dict[str, str]] = None

    def orchestrate(self) -> str:
        """Main entry point - orchestrate the entire query build.

        Returns:
            Complete SQL query string
        """
        # Phase 1: Object reference CTEs (always first if needed)
        self._build_object_ref_ctes_phase()

        # Phase 2: Table-specific CTEs (filter optimization or include_running)
        self._build_table_specific_ctes_phase()

        # Phase 3: Build main query
        main_query_sql = self._build_main_query_phase()

        # Phase 4: Cost CTEs (always last if needed)
        if self.query.include_costs:
            # Add main query as all_calls CTE
            self.cte_registry.add_cte("all_calls", main_query_sql)

            # Build cost query - this returns CTEs + final select
            cost_query_sql = self._build_cost_query_sql()

            # Phase 5: Render WITH clause + cost CTEs + final select
            # The cost_query_sql already includes "llm_usage AS (...), ranked_prices AS (...) SELECT ..."
            # We need to merge it with our existing CTEs
            if self.cte_registry.has_ctes():
                # We have existing CTEs, so we need to append cost CTEs
                rendered_ctes = self.cte_registry.render()
                # Remove the trailing newline and add comma for continuation
                rendered_ctes = rendered_ctes.rstrip("\n") + ",\n"
                return rendered_ctes + cost_query_sql
            else:
                # No existing CTEs, cost_query will add its own WITH
                return "WITH " + cost_query_sql

        # Phase 5: Render (no costs)
        return self.cte_registry.render() + main_query_sql

    def _build_object_ref_ctes_phase(self) -> None:
        """Phase 1: Build object reference CTEs if needed."""
        object_ref_conditions = get_all_object_ref_conditions(
            self.query.query_conditions,
            self.query.order_fields,
            self.query.expand_columns,
        )

        if not object_ref_conditions:
            return

        # Build CTEs and get field mapping
        object_join_cte_sql, self._field_to_object_join_alias_map = (
            build_object_ref_ctes(self.pb, self.query.project_id, object_ref_conditions)
        )

        if object_join_cte_sql:
            # Parse and add individual CTEs from the comma-separated string
            # Format: "cte1 AS (...), cte2 AS (...)"
            self._parse_and_add_object_ref_ctes(object_join_cte_sql)

    def _parse_and_add_object_ref_ctes(self, cte_sql: str) -> None:
        """Parse comma-separated CTEs and add them to registry."""
        # Split by ", " pattern while preserving CTE content
        # This is a simple parser - assumes well-formed SQL from build_object_ref_ctes
        parts = []
        depth = 0
        current = []

        for char in cte_sql:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            current.append(char)

            # Split on comma at depth 0
            if char == "," and depth == 0:
                parts.append("".join(current[:-1]).strip())
                current = []

        # Add remaining
        if current:
            parts.append("".join(current).strip())

        # Add each CTE to registry
        for part in parts:
            if " AS " not in part:
                continue
            name, sql = part.split(" AS ", 1)
            name = name.strip()
            # Remove outer parentheses from SQL
            sql = sql.strip()
            if sql.startswith("(") and sql.endswith(")"):
                sql = sql[1:-1].strip()
            self.cte_registry.add_cte(name, sql)

    @abstractmethod
    def _build_table_specific_ctes_phase(self) -> None:
        """Phase 2: Build table-specific CTEs.

        For calls_merged: filter optimization CTE
        For calls_complete: include_running CTEs
        """
        pass

    @abstractmethod
    def _build_main_query_phase(self) -> str:
        """Phase 3: Build the main query.

        Returns:
            Main query SQL (without CTEs)
        """
        pass

    def _build_cost_query_sql(self) -> str:
        """Build cost query CTEs and final select.

        Returns:
            Cost CTEs and final select SQL (without WITH prefix)
        """
        # Build cost query components
        order_by_fields = [
            tsi.SortBy(
                field=sort_by.field.field,
                direction=cast(Literal["asc", "desc"], sort_by.direction.lower()),
            )
            for sort_by in self.query.order_fields
        ]
        select_fields = [field.field for field in self.query.select_fields]

        # cost_query returns: "llm_usage AS (...), ranked_prices AS (...) <final_select>"
        # This assumes "all_calls" CTE already exists in the registry
        return cost_query(
            self.pb, "all_calls", self.query.project_id, select_fields, order_by_fields
        )

    def _determine_needs_feedback(self) -> bool:
        """Check if query needs feedback join."""
        from weave.trace_server.calls_query_builder.calls_query_builder import (
            CallsMergedFeedbackPayloadField,
        )

        for condition in self.query.query_conditions:
            if condition.is_feedback():
                return True
        for order_field in self.query.order_fields:
            if isinstance(order_field.field, CallsMergedFeedbackPayloadField):
                return True
        return False

    def _get_field_to_object_join_alias_map(self) -> Optional[dict[str, str]]:
        """Get the field to object join alias map (built in phase 1)."""
        return self._field_to_object_join_alias_map


class CallsMergedOrchestrator(BaseQueryOrchestrator):
    """Orchestrator for calls_merged table queries.

    Handles:
    - Predicate pushdown optimization via filtered_calls CTE
    - Aggregation (GROUP BY)
    - Running calls filtering
    """

    def _build_table_specific_ctes_phase(self) -> None:
        """Build filter optimization CTE if beneficial."""
        if not self._should_optimize():
            return

        # Build filtered_calls CTE for predicate pushdown
        filter_cte_sql = self._build_filter_optimization_cte()
        self.cte_registry.add_cte("filtered_calls", filter_cte_sql)

    def _build_main_query_phase(self) -> str:
        """Build main calls_merged query with GROUP BY."""
        table_alias = "calls_merged"

        # Build select fields
        select_fields_sql = ", ".join(
            field.as_select_sql(self.pb, table_alias)
            for field in self.query.select_fields
        )

        # Build filter conditions (for HAVING)
        filter_conditions = build_filter_conditions(
            self.pb,
            self.query.query_conditions,
            self.query.hardcoded_filter,
            table_alias,
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        # Build joins
        joins = build_query_joins(
            self.pb,
            table_alias,
            self.project_id_param_slot,
            needs_feedback=self._determine_needs_feedback(),
            include_storage_size=self.query.include_storage_size,
            include_total_storage_size=self.query.include_total_storage_size,
            order_fields=self.query.order_fields,
            expand_columns=self.query.expand_columns,
            field_to_object_join_alias_map=self._get_field_to_object_join_alias_map(),
        )

        # Build ORDER BY
        order_by_clause = build_order_by_clause(
            self.pb,
            self.query.order_fields,
            table_alias,
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        # Build LIMIT/OFFSET
        limit_clause, offset_clause = build_limit_offset_clause(
            self.query.limit, self.query.offset
        )

        # Build WHERE conditions (pre-GROUP BY optimizations)
        where_conditions = [f"{table_alias}.project_id = {self.project_id_param_slot}"]

        # Add id filter if filtered_calls CTE exists
        if "filtered_calls" in self.cte_registry.get_cte_names():
            where_conditions.append(f"({table_alias}.id IN filtered_calls)")

        # Add optimization filters
        where_conditions.extend(self._build_optimization_filters(table_alias))

        # Add running filter if needed
        if not self.query.include_running:
            where_conditions.append(f"any({table_alias}.ended_at) IS NULL")

        # Build HAVING clause
        having_clause = ""
        if filter_conditions:
            having_clause = f"HAVING {combine_conditions(filter_conditions, 'AND')}"

        # Assemble query
        joins_sql = "\n".join(joins)
        where_sql = "WHERE " + combine_conditions(where_conditions, "AND")
        order_sql = order_by_clause or ""

        return safely_format_sql(
            f"""
            SELECT {select_fields_sql}
            FROM {table_alias}
            {joins_sql}
            {where_sql}
            GROUP BY ({table_alias}.project_id, {table_alias}.id)
            {having_clause}
            {order_sql}
            {limit_clause}
            {offset_clause}
            """,
            logger,
        )

    def _should_optimize(self) -> bool:
        """Determine if predicate pushdown optimization should be used."""
        has_heavy_select = any(field.is_heavy() for field in self.query.select_fields)
        has_heavy_filter = any(
            condition.is_heavy() for condition in self.query.query_conditions
        )
        has_heavy_order = any(
            order_field.field.is_heavy() for order_field in self.query.order_fields
        )
        has_heavy_fields = has_heavy_select or has_heavy_filter or has_heavy_order

        has_light_filter = (
            self.query.hardcoded_filter and self.query.hardcoded_filter.is_useful()
        )
        has_light_query = any(
            not condition.is_heavy() for condition in self.query.query_conditions
        )
        has_light_order_filter = (
            bool(self.query.order_fields)
            and self.query.limit is not None
            and not has_heavy_filter
            and not has_heavy_order
        )

        predicate_pushdown_possible = (
            has_light_filter or has_light_query or has_light_order_filter
        )

        # Also check if object refs or costs are involved
        object_ref_conditions = get_all_object_ref_conditions(
            self.query.query_conditions,
            self.query.order_fields,
            self.query.expand_columns,
        )

        return (
            (has_heavy_fields and predicate_pushdown_possible)
            or self.query.include_costs
            or bool(object_ref_conditions)
        )

    def _build_filter_optimization_cte(self) -> str:
        """Build the filtered_calls CTE for optimization."""
        # Build filter CTE directly
        table_alias = "calls_merged"

        # Build filter conditions
        filter_conditions = build_filter_conditions(
            self.pb,
            self.query.query_conditions,
            self.query.hardcoded_filter,
            table_alias,
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        # Build WHERE conditions
        where_conditions = [f"{table_alias}.project_id = {self.project_id_param_slot}"]
        where_conditions.extend(self._build_optimization_filters(table_alias))

        # Build HAVING if needed
        having_clause = ""
        if filter_conditions:
            having_clause = f"HAVING {combine_conditions(filter_conditions, 'AND')}"

        # Build ORDER BY
        order_by_clause = build_order_by_clause(
            self.pb,
            self.query.order_fields,
            table_alias,
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        limit_clause, offset_clause = build_limit_offset_clause(
            self.query.limit, self.query.offset
        )

        where_sql = combine_conditions(where_conditions, "AND")

        return safely_format_sql(
            f"""
            SELECT id
            FROM {table_alias}
            WHERE {where_sql}
            GROUP BY ({table_alias}.project_id, {table_alias}.id)
            {having_clause}
            {order_by_clause or ""}
            {limit_clause}
            {offset_clause}
            """,
            logger,
        )

    def _build_optimization_filters(self, table_alias: str) -> list[str]:
        """Build WHERE clause optimization filters."""
        from weave.trace_server.calls_query_builder.calls_query_builder import (
            process_object_refs_filter_to_opt_sql,
            process_op_name_filter_to_sql,
            process_parent_ids_filter_to_sql,
            process_ref_filters_to_sql,
            process_thread_id_filter_to_sql,
            process_trace_id_filter_to_sql,
            process_trace_roots_only_filter_to_sql,
            process_turn_id_filter_to_sql,
            process_wb_run_ids_filter_to_sql,
        )
        from weave.trace_server.calls_query_builder.optimization_builder import (
            process_query_to_optimization_sql,
        )

        filters = []

        # Add op_name filter
        op_name_sql = process_op_name_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if op_name_sql:
            filters.append(op_name_sql.removeprefix(" AND "))

        # Add trace_id filter
        trace_id_sql = process_trace_id_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if trace_id_sql:
            filters.append(trace_id_sql.removeprefix(" AND "))

        # Add thread_id filter
        thread_id_sql = process_thread_id_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if thread_id_sql:
            filters.append(thread_id_sql.removeprefix(" AND "))

        # Add turn_id filter
        turn_id_sql = process_turn_id_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if turn_id_sql:
            filters.append(turn_id_sql.removeprefix(" AND "))

        # Add wb_run_id filter
        wb_run_id_sql = process_wb_run_ids_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if wb_run_id_sql:
            filters.append(wb_run_id_sql.removeprefix(" AND "))

        # Add ref filters
        ref_filter_sql = process_ref_filters_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if ref_filter_sql:
            filters.append(ref_filter_sql.removeprefix(" AND "))

        # Add trace_roots_only filter
        trace_roots_only_sql = process_trace_roots_only_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if trace_roots_only_sql:
            filters.append(trace_roots_only_sql.removeprefix(" AND "))

        # Add parent_ids filter
        parent_ids_sql = process_parent_ids_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if parent_ids_sql:
            filters.append(parent_ids_sql.removeprefix(" AND "))

        # Filter out object ref conditions for optimization
        non_object_ref_conditions = []
        object_ref_fields_consumed: set[str] = set()
        for condition in self.query.query_conditions:
            if not (
                self.query.expand_columns
                and is_object_ref_operand(condition.operand, self.query.expand_columns)
            ):
                non_object_ref_conditions.append(condition)
            else:
                if condition._consumed_fields is not None:
                    object_ref_fields_consumed.update(
                        f.field for f in condition._consumed_fields
                    )

        # Add object refs optimization filter
        object_refs_filter_sql = process_object_refs_filter_to_opt_sql(
            self.pb, table_alias, object_ref_fields_consumed
        )
        if object_refs_filter_sql:
            filters.append(object_refs_filter_sql.removeprefix(" AND "))

        # Add optimization conditions from query
        optimization_conditions = process_query_to_optimization_sql(
            non_object_ref_conditions, self.pb, table_alias
        )
        if optimization_conditions.sortable_datetime_filters_sql:
            filters.append(
                optimization_conditions.sortable_datetime_filters_sql.removeprefix(
                    " AND "
                )
            )
        if optimization_conditions.heavy_filter_opt_sql:
            filters.append(
                optimization_conditions.heavy_filter_opt_sql.removeprefix(" AND ")
            )

        # Add call_ids optimization if present
        if self.query.hardcoded_filter and self.query.hardcoded_filter.filter.call_ids:
            id_mask_sql = f"(calls_merged.id IN {param_slot(self.pb.add_param(self.query.hardcoded_filter.filter.call_ids), 'Array(String)')})"
            filters.append(id_mask_sql)

        return filters


class CallsCompleteOrchestrator(BaseQueryOrchestrator):
    """Orchestrator for calls_complete table queries.

    Handles:
    - include_running=True via UNION ALL with call_starts
    - No aggregation (direct field access)
    - complete and parts_only CTEs
    """

    def _build_table_specific_ctes_phase(self) -> None:
        """Build include_running CTEs if needed."""
        if not self.query.include_running:
            # Build optimization CTE for complete-only queries
            if self._should_use_filter_cte():
                filter_cte_sql = self._build_filtered_calls_cte()
                self.cte_registry.add_cte("filtered_calls", filter_cte_sql)
            return

        # Build CTEs for complete and running calls
        complete_cte_sql = self._build_complete_cte()
        parts_only_cte_sql = self._build_parts_only_cte()

        self.cte_registry.add_cte("complete", complete_cte_sql)
        self.cte_registry.add_cte("parts_only", parts_only_cte_sql)

    def _build_main_query_phase(self) -> str:
        """Build main query - UNION ALL if include_running, else simple SELECT."""
        if self.query.include_running:
            return self._build_union_all_query()
        else:
            return self._build_simple_query()

    def _should_use_filter_cte(self) -> bool:
        """Determine if we should use a filter CTE for optimization."""
        # Use filter CTE if we have heavy fields (inputs_dump or output_dump)
        select_fields_str = ", ".join(f.field for f in self.query.select_fields)
        return "inputs_dump" in select_fields_str or "output_dump" in select_fields_str

    def _build_filtered_calls_cte(self) -> str:
        """Build filtered_calls CTE for complete-only queries."""
        table_alias = "calls_complete"

        # Build filter conditions
        filter_conditions = build_filter_conditions(
            self.pb,
            self.query.query_conditions,
            self.query.hardcoded_filter,
            table_alias,
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        # Build WHERE conditions
        where_conditions = [f"project_id = {self.project_id_param_slot}"]
        where_conditions.extend(filter_conditions)
        where_conditions.extend(self._build_optimization_filters(table_alias))

        where_sql = combine_conditions(where_conditions, "AND")

        # Build ORDER BY
        order_by_clause = build_order_by_clause(
            self.pb,
            self.query.order_fields,
            table_alias,
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        limit_clause, offset_clause = build_limit_offset_clause(
            self.query.limit, self.query.offset
        )

        return safely_format_sql(
            f"""
            SELECT id FROM {table_alias}
            WHERE {where_sql}
            {order_by_clause or ""}
            {limit_clause}
            {offset_clause}
            """,
            logger,
        )

    def _build_complete_cte(self) -> str:
        """Build CTE to get IDs of complete calls.

        Note: We don't limit here because we need to combine with running calls
        and deduplicate before limiting to ensure we get the most recent N calls overall.
        """
        table_alias = "calls_complete"

        # Build filter conditions
        filter_conditions = build_filter_conditions(
            self.pb,
            self.query.query_conditions,
            self.query.hardcoded_filter,
            table_alias,
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        # Build WHERE conditions
        where_conditions = [f"project_id = {self.project_id_param_slot}"]
        where_conditions.extend(filter_conditions)
        where_conditions.extend(self._build_optimization_filters(table_alias))

        where_sql = combine_conditions(where_conditions, "AND")

        return safely_format_sql(
            f"""
            SELECT id
            FROM {table_alias}
            WHERE {where_sql}
            """,
            logger,
        )

    def _build_parts_only_cte(self) -> str:
        """Build CTE to get IDs of running calls (not in complete).

        Note: We don't limit here because we need to combine with complete calls
        and deduplicate before limiting to ensure we get the most recent N calls overall.
        """
        table_alias = "call_starts"

        # Build filter conditions compatible with call_starts
        filter_conditions = self._build_call_starts_compatible_filters()

        # Build WHERE conditions
        where_conditions = [f"project_id = {self.project_id_param_slot}"]
        where_conditions.extend(filter_conditions)
        where_conditions.append("id NOT IN (SELECT id FROM complete)")
        where_conditions.extend(self._build_optimization_filters(table_alias))

        where_sql = combine_conditions(where_conditions, "AND")

        return safely_format_sql(
            f"""
            SELECT id
            FROM {table_alias}
            WHERE {where_sql}
            """,
            logger,
        )

    def _build_union_all_query(self) -> str:
        """Build UNION ALL query for complete + running calls.

        Uses a subquery with deduplication to ensure:
        1. No duplicates between complete and running calls
        2. Complete calls are preferred over running calls (they have more data)
        3. We get exactly the most recent N calls overall

        Strategy: Add a priority field (1 for complete, 0 for running) and use
        ROW_NUMBER() to deduplicate, keeping the highest priority version.
        """
        # Build complete calls SELECT with priority
        complete_select = self._build_complete_select_with_priority(priority=1)

        # Build running calls SELECT with priority (with NULL for missing fields)
        running_select = self._build_running_select_with_priority(priority=0)

        # Build ORDER BY that works on UNION ALL result
        order_by_clause = build_order_by_clause(
            self.pb,
            self.query.order_fields,
            "calls_complete",
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        # Strip table prefixes from ORDER BY (UNION ALL doesn't have table aliases)
        if order_by_clause:
            order_by_clause = re.sub(
                r"\b(calls_complete|call_starts|j\d+)\.", "", order_by_clause
            )
        else:
            order_by_clause = "ORDER BY started_at DESC"

        limit_clause, offset_clause = build_limit_offset_clause(
            self.query.limit, self.query.offset
        )

        # Get list of select fields for the outer SELECT
        select_fields = ", ".join(
            field.field if hasattr(field, "field") else str(field)
            for field in self.query.select_fields
        )

        # Wrap in subquery with deduplication using ROW_NUMBER()
        # Higher priority (complete = 1) will be selected over lower priority (running = 0)
        return safely_format_sql(
            f"""
            SELECT {select_fields}
            FROM (
                SELECT
                    {select_fields},
                    ROW_NUMBER() OVER (PARTITION BY id ORDER BY _priority DESC) AS _rn
                FROM (
                    {complete_select}
                    UNION ALL
                    {running_select}
                )
            )
            WHERE _rn = 1
            {order_by_clause}
            {limit_clause}
            {offset_clause}
            """,
            logger,
        )

    def _build_complete_select(self) -> str:
        """Build SELECT for complete calls."""
        return self._build_complete_select_with_priority(priority=None)

    def _build_complete_select_with_priority(self, priority: Optional[int]) -> str:
        """Build SELECT for complete calls, optionally with a priority field."""
        table_alias = "calls_complete"

        select_fields_sql = ", ".join(
            field.as_select_sql(self.pb, table_alias)
            for field in self.query.select_fields
        )

        # Add priority field if specified
        if priority is not None:
            select_fields_sql = f"{select_fields_sql}, {priority} AS _priority"

        joins = build_query_joins(
            self.pb,
            table_alias,
            self.project_id_param_slot,
            needs_feedback=self._determine_needs_feedback(),
            include_storage_size=self.query.include_storage_size,
            include_total_storage_size=self.query.include_total_storage_size,
            order_fields=self.query.order_fields,
            expand_columns=self.query.expand_columns,
            field_to_object_join_alias_map=self._get_field_to_object_join_alias_map(),
        )

        joins_sql = "\n".join(joins)

        where_conditions = [
            f"{table_alias}.project_id = {self.project_id_param_slot}",
            f"{table_alias}.id IN (SELECT id FROM complete)",
        ]
        where_conditions.extend(self._build_optimization_filters(table_alias))

        where_sql = combine_conditions(where_conditions, "AND")

        return safely_format_sql(
            f"""
            SELECT {select_fields_sql}
            FROM {table_alias}
            {joins_sql}
            WHERE {where_sql}
            """,
            logger,
        )

    def _build_running_select(self) -> str:
        """Build SELECT for running calls with NULL for missing fields."""
        return self._build_running_select_with_priority(priority=None)

    def _build_running_select_with_priority(self, priority: Optional[int]) -> str:
        """Build SELECT for running calls with NULL for missing fields, optionally with a priority field."""
        from weave.trace_server.calls_query_builder.calls_query_builder import (
            CallsCompleteField,
        )

        table_alias = "call_starts"

        # Fields not in call_starts with their proper types
        # For dump fields, use empty JSON object instead of NULL
        # For array fields, use empty array [] instead of NULL
        missing_fields_with_types = {
            "ended_at": "CAST(NULL AS Nullable(DateTime64(3)))",
            "output_dump": "'{}'",  # Empty JSON object for dump fields
            "summary_dump": "'{}'",  # Empty JSON object for dump fields
            "exception": "CAST(NULL AS Nullable(String))",
            "output_refs": "[]",  # Empty array instead of NULL
        }

        select_parts = []
        for field in self.query.select_fields:
            if isinstance(field, CallsCompleteField):
                field_name = field.field
                if field_name in missing_fields_with_types:
                    select_parts.append(
                        f"{missing_fields_with_types[field_name]} AS {field_name}"
                    )
                else:
                    select_parts.append(f"{table_alias}.{field_name} AS {field_name}")
            else:
                # Handle other field types
                field_name_attr: Optional[str] = getattr(field, "field", None)
                if field_name_attr and field_name_attr in missing_fields_with_types:
                    select_parts.append(
                        f"{missing_fields_with_types[field_name_attr]} AS {field_name_attr}"
                    )
                elif field_name_attr:
                    select_parts.append(
                        f"{table_alias}.{field_name_attr} AS {field_name_attr}"
                    )

        # Add priority field if specified
        if priority is not None:
            select_parts.append(f"{priority} AS _priority")

        select_fields_sql = ", ".join(select_parts)

        where_conditions = [
            f"{table_alias}.project_id = {self.project_id_param_slot}",
            f"{table_alias}.id IN (SELECT id FROM parts_only)",
        ]
        where_conditions.extend(self._build_optimization_filters(table_alias))

        where_sql = combine_conditions(where_conditions, "AND")

        return safely_format_sql(
            f"""
            SELECT {select_fields_sql}
            FROM {table_alias}
            WHERE {where_sql}
            """,
            logger,
        )

    def _build_simple_query(self) -> str:
        """Build simple SELECT when include_running=False."""
        table_alias = "calls_complete"

        select_fields_sql = ", ".join(
            field.as_select_sql(self.pb, table_alias)
            for field in self.query.select_fields
        )

        # Build filter conditions
        filter_conditions = build_filter_conditions(
            self.pb,
            self.query.query_conditions,
            self.query.hardcoded_filter,
            table_alias,
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        # Build joins
        joins = build_query_joins(
            self.pb,
            table_alias,
            self.project_id_param_slot,
            needs_feedback=self._determine_needs_feedback(),
            include_storage_size=self.query.include_storage_size,
            include_total_storage_size=self.query.include_total_storage_size,
            order_fields=self.query.order_fields,
            expand_columns=self.query.expand_columns,
            field_to_object_join_alias_map=self._get_field_to_object_join_alias_map(),
        )

        # Build ORDER BY
        order_by_clause = build_order_by_clause(
            self.pb,
            self.query.order_fields,
            table_alias,
            self.query.expand_columns,
            self._get_field_to_object_join_alias_map(),
        )

        # Build LIMIT/OFFSET
        limit_clause, offset_clause = build_limit_offset_clause(
            self.query.limit, self.query.offset
        )

        joins_sql = "\n".join(joins)

        # Build WHERE conditions
        where_conditions = [f"{table_alias}.project_id = {self.project_id_param_slot}"]

        # If filtered_calls CTE exists, use it
        if "filtered_calls" in self.cte_registry.get_cte_names():
            where_conditions.append(
                f"{table_alias}.id IN (SELECT id FROM filtered_calls)"
            )
        else:
            where_conditions.extend(filter_conditions)
            where_conditions.extend(self._build_optimization_filters(table_alias))

        where_sql = combine_conditions(where_conditions, "AND")
        order_sql = order_by_clause or ""

        return safely_format_sql(
            f"""
            SELECT {select_fields_sql}
            FROM {table_alias}
            {joins_sql}
            WHERE {where_sql}
            {order_sql}
            {limit_clause}
            {offset_clause}
            """,
            logger,
        )

    def _build_call_starts_compatible_filters(self) -> list[str]:
        """Build filters compatible with call_starts table.

        Filters out conditions that reference fields not in call_starts.
        """
        # Fields not available in call_starts
        complete_only_fields = {
            "ended_at",
            "output_dump",
            "summary_dump",
            "exception",
            "output_refs",
        }

        compatible_conditions = []

        for condition in self.query.query_conditions:
            # Check if condition references complete-only fields
            if condition._consumed_fields:
                has_complete_only = any(
                    f.field in complete_only_fields for f in condition._consumed_fields
                )
                if not has_complete_only:
                    condition_sql = condition.as_sql(
                        self.pb,
                        "call_starts",
                        expand_columns=self.query.expand_columns,
                        field_to_object_join_alias_map=self._get_field_to_object_join_alias_map(),
                    )
                    compatible_conditions.append(condition_sql)

        # Add hardcoded filter if present
        if self.query.hardcoded_filter:
            hardcoded_sql = self.query.hardcoded_filter.as_sql(self.pb, "call_starts")
            if hardcoded_sql:
                compatible_conditions.append(hardcoded_sql)

        return compatible_conditions

    def _build_optimization_filters(self, table_alias: str) -> list[str]:
        """Build optimization filters (trace_id, op_name, etc.)."""
        from weave.trace_server.calls_query_builder.calls_query_builder import (
            process_object_refs_filter_to_opt_sql,
            process_op_name_filter_to_sql,
            process_trace_id_filter_to_sql,
            process_trace_roots_only_filter_to_sql,
        )

        filters = []

        # Add trace_id filter
        trace_id_sql = process_trace_id_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if trace_id_sql:
            filters.append(trace_id_sql.removeprefix(" AND "))

        # Add trace_roots_only filter
        trace_roots_only_sql = process_trace_roots_only_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if trace_roots_only_sql:
            filters.append(trace_roots_only_sql.removeprefix(" AND "))

        # Add op_name filter
        op_name_sql = process_op_name_filter_to_sql(
            self.query.hardcoded_filter, self.pb, table_alias
        )
        if op_name_sql:
            filters.append(op_name_sql.removeprefix(" AND "))

        # Add object refs optimization
        object_ref_fields_consumed: set[str] = set()
        for condition in self.query.query_conditions:
            if (
                self.query.expand_columns
                and is_object_ref_operand(condition.operand, self.query.expand_columns)
                and condition._consumed_fields is not None
            ):
                object_ref_fields_consumed.update(
                    f.field for f in condition._consumed_fields
                )

        object_refs_filter_sql = process_object_refs_filter_to_opt_sql(
            self.pb, table_alias, object_ref_fields_consumed
        )
        if object_refs_filter_sql:
            filters.append(object_refs_filter_sql.removeprefix(" AND "))

        return filters
