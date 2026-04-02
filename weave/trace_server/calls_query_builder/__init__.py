"""Calls query builder package.

Provides query building abstractions for the ClickHouse calls table,
including field definitions, condition processing, filter handling,
query orchestration, and stats/mutation query builders.

Import from the specific submodules for the symbols you need:
- calls_query_builder.fields - Field classes and registry
- calls_query_builder.conditions - Query condition processing
- calls_query_builder.hardcoded_filters - CallsFilter to SQL
- calls_query_builder.calls_query_builder - CallsQuery orchestrator
- calls_query_builder.stats - Stats query builders
- calls_query_builder.mutations - UPDATE/DELETE query builders
- calls_query_builder.cte - CTE helpers
- calls_query_builder.utils - SQL utilities
"""
