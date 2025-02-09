import pytest

from weave.trace_server.objects_query_builder import (
    ObjectMetadataQueryBuilder,
    _make_conditions_part,
    _make_limit_part,
    _make_object_id_conditions_part,
    _make_offset_part,
    _make_sort_part,
    make_objects_val_query_and_parameters,
)
from weave.tsi import trace_server_interface as tsi


def test_make_limit_part():
    assert _make_limit_part(None) == ""
    assert _make_limit_part(10) == "LIMIT 10"
    assert _make_limit_part(0) == "LIMIT 0"


def test_make_offset_part():
    assert _make_offset_part(None) == ""
    assert _make_offset_part(5) == "OFFSET 5"
    assert _make_offset_part(0) == "OFFSET 0"


def test_make_sort_part():
    assert _make_sort_part(None) == ""
    assert _make_sort_part([]) == ""

    sort_by = [tsi.SortBy(field="created_at", direction="asc")]
    assert _make_sort_part(sort_by) == "ORDER BY created_at ASC"

    sort_by = [
        tsi.SortBy(field="created_at", direction="desc"),
        tsi.SortBy(field="object_id", direction="asc"),
    ]
    assert _make_sort_part(sort_by) == "ORDER BY created_at DESC, object_id ASC"

    # Invalid sort fields should be ignored
    sort_by = [tsi.SortBy(field="invalid_field", direction="asc")]
    assert _make_sort_part(sort_by) == ""


def test_make_conditions_part():
    assert _make_conditions_part(None) == ""
    assert _make_conditions_part([]) == ""
    assert _make_conditions_part(["condition1"]) == "WHERE condition1"
    assert (
        _make_conditions_part(["condition1", "condition2"])
        == "WHERE ((condition1) AND (condition2))"
    )


def test_make_object_id_conditions_part():
    assert _make_object_id_conditions_part(None) == ""
    assert _make_object_id_conditions_part([]) == ""
    assert _make_object_id_conditions_part(["id = 1"]) == " AND id = 1"
    assert (
        _make_object_id_conditions_part(["id = 1", "id = 2"])
        == " AND ((id = 1) AND (id = 2))"
    )


def test_object_query_builder_basic():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    assert "project_id = {project_id: String}" in builder.make_metadata_query()
    assert builder.parameters["project_id"] == "test_project"


def test_object_query_builder_add_digest_condition():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")

    # Test latest digest
    builder.add_digests_conditions("latest")
    assert "is_latest = 1" in builder.conditions_part

    # Test specific digest
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_digests_conditions("abc123")
    assert "digest = {version_digest_0: String}" in builder.conditions_part
    assert builder.parameters["version_digest_0"] == "abc123"


def test_object_query_builder_add_object_ids_condition():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")

    # Test single object ID
    builder.add_object_ids_condition(["obj1"])
    assert "object_id = {object_id: String}" in builder.object_id_conditions_part
    assert builder.parameters["object_id"] == "obj1"

    # Test multiple object IDs
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_object_ids_condition(["obj1", "obj2"])
    assert (
        "object_id IN {object_ids: Array(String)}" in builder.object_id_conditions_part
    )
    assert builder.parameters["object_ids"] == ["obj1", "obj2"]


def test_object_query_builder_add_is_op_condition():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_is_op_condition(True)
    assert "is_op = 1" in builder.conditions_part


def test_object_query_builder_limit_offset():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    assert builder.limit_part == ""
    assert builder.offset_part == ""

    builder.set_limit(10)
    builder.set_offset(5)
    assert builder.limit_part == "LIMIT 10"
    assert builder.offset_part == "OFFSET 5"

    # Test invalid values
    with pytest.raises(ValueError):
        builder.set_limit(-1)
    with pytest.raises(ValueError):
        builder.set_offset(-1)
    with pytest.raises(ValueError):
        builder.set_limit(5)  # Limit already set
    with pytest.raises(ValueError):
        builder.set_offset(10)  # Offset already set


def test_object_query_builder_sort():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_order("created_at", "DESC")
    assert builder.sort_part == "ORDER BY created_at DESC"

    with pytest.raises(ValueError):
        builder.add_order("created_at", "INVALID")


STATIC_METADATA_QUERY_PART = """
SELECT
    project_id,
    object_id,
    created_at,
    refs,
    kind,
    base_object_class,
    digest,
    version_index,
    is_latest,
    deleted_at,
    wb_user_id,
    version_count,
    is_op
FROM (
    SELECT
        project_id,
        object_id,
        created_at,
        deleted_at,
        kind,
        base_object_class,
        refs,
        digest,
        wb_user_id,
        is_op,
        row_number() OVER (
            PARTITION BY project_id,
            kind,
            object_id
            ORDER BY created_at ASC
        ) - 1 AS version_index,
        count(*) OVER (
            PARTITION BY project_id, kind, object_id
        ) as version_count,
        row_number() OVER (
            PARTITION BY project_id, kind, object_id
            ORDER BY (deleted_at IS NULL) DESC, created_at DESC
        ) AS row_num,
        if (row_num = 1, 1, 0) AS is_latest
    FROM (
        SELECT
            project_id,
            object_id,
            created_at,
            deleted_at,
            kind,
            base_object_class,
            refs,
            digest,
            wb_user_id,
            if (kind = 'op', 1, 0) AS is_op,
            row_number() OVER (
                PARTITION BY project_id,
                kind,
                object_id,
                digest
                ORDER BY created_at ASC
            ) AS rn
        FROM object_versions"""


def test_object_query_builder_metadata_query_basic():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_digests_conditions("latest")

    query = builder.make_metadata_query()
    parameters = builder.parameters

    expected_query = f"""{STATIC_METADATA_QUERY_PART}
        WHERE project_id = {{project_id: String}}
    )
    WHERE rn = 1
)
WHERE ((is_latest = 1) AND (deleted_at IS NULL))
ORDER BY created_at ASC"""

    assert query == expected_query
    assert parameters == {"project_id": "test_project"}


def test_object_query_builder_metadata_query_with_limit_offset_sort():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")

    limit = 10
    offset = 5

    builder.set_limit(limit)
    builder.set_offset(offset)
    builder.add_order("created_at", "desc")
    builder.add_object_ids_condition(["object_1"])
    builder.add_digests_conditions("digestttttttttttttttt", "another-one", "v2")
    builder.add_base_object_classes_condition(["Model", "Model2"])

    query = builder.make_metadata_query()
    parameters = builder.parameters

    expected_query = f"""{STATIC_METADATA_QUERY_PART}
        WHERE project_id = {{project_id: String}} AND object_id = {{object_id: String}}
    )
    WHERE rn = 1
)
WHERE ((((digest = {{version_digest_0: String}}) OR (digest = {{version_digest_1: String}}) OR (version_index = {{version_index_2: Int64}}))) AND (base_object_class IN {{base_object_classes: Array(String)}}) AND (deleted_at IS NULL))
ORDER BY created_at DESC
LIMIT 10
OFFSET 5"""

    assert query == expected_query
    assert parameters == {
        "project_id": "test_project",
        "object_id": "object_1",
        "version_digest_0": "digestttttttttttttttt",
        "version_digest_1": "another-one",
        "version_index_2": 2,
        "base_object_classes": ["Model", "Model2"],
    }


def test_objects_query_metadata_op():
    builder = ObjectMetadataQueryBuilder(project_id="test_project")
    builder.add_is_op_condition(True)
    builder.add_object_ids_condition(["my_op"])
    builder.add_digests_conditions("v3")

    query = builder.make_metadata_query()
    parameters = builder.parameters

    expected_query = f"""{STATIC_METADATA_QUERY_PART}
        WHERE project_id = {{project_id: String}} AND object_id = {{object_id: String}}
    )
    WHERE rn = 1
)
WHERE ((is_op = 1) AND (version_index = {{version_index_0: Int64}}) AND (deleted_at IS NULL))
ORDER BY created_at ASC"""

    assert query == expected_query
    assert parameters == {
        "project_id": "test_project",
        "object_id": "my_op",
        "version_index_0": 3,
    }


def test_make_objects_val_query_and_parameters():
    project_id = "test_project"
    object_ids = ["object_1"]
    digests = ["digestttttttttttttttt", "digestttttttttttttttt2"]

    query, parameters = make_objects_val_query_and_parameters(
        project_id, object_ids, digests
    )

    expected_query = """
        SELECT object_id, digest, any(val_dump)
        FROM object_versions
        WHERE project_id = {project_id: String} AND
            object_id IN {object_ids: Array(String)} AND
            digest IN {digests: Array(String)}
        GROUP BY object_id, digest
    """

    assert query == expected_query
    assert parameters == {
        "project_id": "test_project",
        "object_ids": ["object_1"],
        "digests": ["digestttttttttttttttt", "digestttttttttttttttt2"],
    }
