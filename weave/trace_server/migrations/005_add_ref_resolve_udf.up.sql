-- 'weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$'
-- table_rows = 'weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$'

CREATE OR REPLACE FUNCTION is_object_ref AS (any_thing) -> toTypeName(any_thing) = 'String' AND match(any_thing, 'weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$');
CREATE OR REPLACE FUNCTION parse_object_ref_project_id AS (ref_str) -> regexpExtract(ref_str, 'weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 1);
CREATE OR REPLACE FUNCTION parse_object_ref_object_id AS (ref_str) -> regexpExtract(ref_str, 'weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 2);
CREATE OR REPLACE FUNCTION parse_object_ref_version_digest AS (ref_str) -> regexpExtract(ref_str, 'weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 3);
CREATE OR REPLACE FUNCTION parse_object_ref_extra AS (ref_str) -> regexpExtract(ref_str, 'weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 4);

CREATE OR REPLACE FUNCTION is_table_row_ref AS (any_thing) -> toTypeName(any_thing) = 'String' AND match(any_thing, 'weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$');
CREATE OR REPLACE FUNCTION parse_table_row_ref_project_id AS (ref_str) -> regexpExtract(ref_str, 'weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 1);
CREATE OR REPLACE FUNCTION parse_table_row_ref_table_digest AS (ref_str) -> regexpExtract(ref_str, 'weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 2);
CREATE OR REPLACE FUNCTION parse_table_row_ref_row_index AS (ref_str) -> toUInt64OrNull(regexpExtract(ref_str, 'weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 3));
CREATE OR REPLACE FUNCTION parse_table_row_ref_extra AS (ref_str) -> regexpExtract(ref_str, 'weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 4);


CREATE OR REPLACE FUNCTION get_object_data AS (project_id, object_id, version_digest) -> (
    SELECT val_dump
    FROM object_versions
    WHERE project_id = project_id AND object_id = object_id AND digest = version_digest
    LIMIT 1
)


CREATE OR REPLACE FUNCTION get_table_data AS (project_id, table_digest, row_index) -> (
    SELECT val_dump
    FROM table_rows
    WHERE project_id = project_id AND digest IN (
        SELECT arrayElement(row_digests, row_index) AS row_digest
        FROM table_rows
        WHERE project_id = project_id AND digest = table_digest
        LIMIT 1
    )
)


CREATE OR REPLACE FUNCTION walk_path AS (raw_data, path) -> (
	-- TODO
	raw_data
)


CREATE OR REPLACE FUNCTION get_data_for_ref AS (project_id, ref_str) -> (
	SELECT 
		multiIf(
			is_object_ref(ref_str) AND parse_object_ref_project_id(ref_str) = project_id,
			walk_path(
				get_object_data(
					project_id,
					parse_object_ref_object_id(ref_str),
					parse_object_ref_version_digest(ref_str)
				),
				parse_object_ref_extra(ref_str)
			),
			is_table_row_ref(ref_str) AND parse_table_row_ref_project_id(ref_str) = project_id,
			walk_path(
				get_table_row_data(
					project_id,
					parse_table_row_ref_table_digest(ref_str),
					parse_table_row_ref_row_index(ref_str)
				),
				parse_object_ref_extra(ref_str)
			),
			NULL
		)
)
