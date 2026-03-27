from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
)
from weave.trace_server.ch_sentinel_values import SENTINEL_DATETIME
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.trace_server_interface import CallsFilter


def test_eval_root_ids_filter_calls_merged() -> None:
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.eval_root_ids = ["eval-1", "eval-2"]
    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        WHERE (calls_merged.parent_id IN {pb_0:Array(String)}
               OR calls_merged.parent_id IN
                 (SELECT calls_merged.id AS id
                  FROM calls_merged
                  PREWHERE calls_merged.project_id = {pb_3:String}
                  WHERE (calls_merged.parent_id IN {pb_2:Array(String)}
                         OR calls_merged.parent_id IS NULL)
                  GROUP BY (calls_merged.project_id,
                            calls_merged.id)
                  HAVING (((any(calls_merged.deleted_at) IS NULL))
                          AND ((NOT ((any(calls_merged.started_at) IS NULL))))
                          AND (any(calls_merged.parent_id) IN {pb_1:Array(String)})))
               OR calls_merged.parent_id IS NULL)
          AND calls_merged.id NOT IN {pb_0:Array(String)}
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {
            "pb_0": ["eval-1", "eval-2"],
            "pb_1": ["eval-1", "eval-2"],
            "pb_2": ["eval-1", "eval-2"],
            "pb_3": "project",
        },
    )


def test_eval_root_ids_filter_calls_complete() -> None:
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.eval_root_ids = ["eval-1", "eval-2"]
    assert_sql(
        cq,
        """
        SELECT calls_complete.id AS id
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_6:String}
        WHERE (calls_complete.parent_id IN {pb_1:Array(String)}
               OR calls_complete.parent_id IN
                 (SELECT calls_complete.id AS id
                  FROM calls_complete
                  PREWHERE calls_complete.project_id = {pb_6:String}
                  WHERE (calls_complete.parent_id IN {pb_4:Array(String)}
                         OR calls_complete.parent_id = {pb_5:String})
                    AND (((calls_complete.deleted_at = {pb_2:DateTime64(3)}))
                         AND (calls_complete.parent_id IN {pb_3:Array(String)}))))
          AND calls_complete.id NOT IN {pb_1:Array(String)}
          AND (calls_complete.deleted_at = {pb_0:DateTime64(3)})
        """,
        {
            "pb_0": SENTINEL_DATETIME,
            "pb_1": ["eval-1", "eval-2"],
            "pb_2": SENTINEL_DATETIME,
            "pb_3": ["eval-1", "eval-2"],
            "pb_4": ["eval-1", "eval-2"],
            "pb_5": "",
            "pb_6": "project",
        },
    )


def test_eval_root_ids_combined_with_op_names_filter() -> None:
    """eval_root_ids composes correctly with other hardcoded filters."""
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.eval_root_ids = ["eval-1"]
    cq.set_hardcoded_filter(HardCodedFilter(filter=CallsFilter(op_names=["my_op"])))
    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_4:String}
        WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
               OR (calls_merged.op_name IS NULL))
          AND (calls_merged.parent_id IN {pb_1:Array(String)}
               OR calls_merged.parent_id IN
                 (SELECT calls_merged.id AS id
                  FROM calls_merged
                  PREWHERE calls_merged.project_id = {pb_4:String}
                  WHERE (calls_merged.parent_id IN {pb_3:Array(String)}
                         OR calls_merged.parent_id IS NULL)
                  GROUP BY (calls_merged.project_id,
                            calls_merged.id)
                  HAVING (((any(calls_merged.deleted_at) IS NULL))
                          AND ((NOT ((any(calls_merged.started_at) IS NULL))))
                          AND (any(calls_merged.parent_id) IN {pb_2:Array(String)})))
               OR calls_merged.parent_id IS NULL)
          AND calls_merged.id NOT IN {pb_1:Array(String)}
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {
            "pb_0": ["my_op"],
            "pb_1": ["eval-1"],
            "pb_2": ["eval-1"],
            "pb_3": ["eval-1"],
            "pb_4": "project",
        },
    )
