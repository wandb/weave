-- '^weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$'
-- table_rows = '^weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$'

CREATE OR REPLACE FUNCTION is_object_ref AS (any_thing) -> toTypeName(any_thing) = 'String' AND match(any_thing, '^weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$');
CREATE OR REPLACE FUNCTION parse_object_ref_project_id AS (ref_str) -> regexpExtract(ref_str, '^weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 1);
CREATE OR REPLACE FUNCTION parse_object_ref_object_id AS (ref_str) -> regexpExtract(ref_str, '^weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 2);
CREATE OR REPLACE FUNCTION parse_object_ref_version_digest AS (ref_str) -> regexpExtract(ref_str, '^weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 3);
CREATE OR REPLACE FUNCTION parse_object_ref_extra AS (ref_str) -> regexpExtract(ref_str, '^weave-trace-internal:\/\/\/([^\/]+)\/object\/([^\/]+):([^\/]+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 4);

CREATE OR REPLACE FUNCTION is_table_row_ref AS (any_thing) -> toTypeName(any_thing) = 'String' AND match(any_thing, '^weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$');
CREATE OR REPLACE FUNCTION parse_table_row_ref_project_id AS (ref_str) -> regexpExtract(ref_str, '^weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 1);
CREATE OR REPLACE FUNCTION parse_table_row_ref_table_digest AS (ref_str) -> regexpExtract(ref_str, '^weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 2);
CREATE OR REPLACE FUNCTION parse_table_row_ref_row_index AS (ref_str) -> toUInt64OrNull(regexpExtract(ref_str, '^weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 3));
CREATE OR REPLACE FUNCTION parse_table_row_ref_extra AS (ref_str) -> regexpExtract(ref_str, '^weave-trace-internal:\/\/\/([^\/]+)\/table\/([^\/]+)\/attr\/rows\/index\/(\d+)((?:\/[^\/]+\/[^\/]+)*)\/?$', 4);

CREATE OR REPLACE FUNCTION every_other_item AS (arr) -> arrayFilter((x, i) -> i % 2 = 0, arr, arrayEnumerate(arr));
CREATE OR REPLACE FUNCTION parse_extra_to_parts AS (extra_str) -> every_other_item(splitByChar('/', trim(BOTH '/' FROM extra_str)));

CREATE OR REPLACE FUNCTION resolve_data_through_refs_for_path AS (ref_or_data_dump, path_parts, allowed_project_id) -> (
	WITH RECURSIVE expand_table AS (
	    SELECT 
	    	FALSE AS last_step_was_object_ref,
	    	FALSE AS last_step_was_table_row_ref,
	    	FALSE AS last_step_was_ref,
	    	ref_or_data_dump AS data_dump,
	    	CAST(path_parts, 'Array(String)') AS remaining_path_paths,
	    	0 AS iteration
	UNION ALL
	    SELECT 
	    	(is_object_ref(expand_table.data_dump) AND parse_object_ref_project_id(expand_table.data_dump) = allowed_project_id) AS last_step_was_object_ref_next,
	    	(is_table_row_ref(expand_table.data_dump) AND parse_table_row_ref_project_id(expand_table.data_dump) = allowed_project_id) AS last_step_was_table_row_ref_next,
	    	last_step_was_object_ref_next OR last_step_was_table_row_ref_next AS last_step_was_ref,
	   		multiIf(
	   			last_step_was_object_ref_next,
	   			object_versions.val_dump,
	   			last_step_was_table_row_ref_next,
	   			table_rows.val_dump,
	   			JSONExtractString(expand_table.data_dump, expand_table.remaining_path_paths[1])
	   		), 
	   		multiIf(
	   			last_step_was_object_ref_next,
	   			arrayConcat(parse_extra_to_parts(parse_object_ref_extra(expand_table.data_dump)), expand_table.remaining_path_paths),
	   			last_step_was_table_row_ref_next,
	   			arrayConcat(parse_extra_to_parts(parse_table_row_ref_extra(expand_table.data_dump)), expand_table.remaining_path_paths),
	   			arraySlice(expand_table.remaining_path_paths, 2)
	   		),
	   		expand_table.iteration + 1
	    FROM expand_table 
	    LEFT JOIN object_versions ON 
	    	object_versions.project_id = allowed_project_id
	    	AND last_step_was_object_ref_next
	    	AND object_versions.object_id = parse_object_ref_object_id(expand_table.data_dump) 
	    	AND object_versions.digest = parse_object_ref_version_digest(expand_table.data_dump)
	    LEFT JOIN tables ON
	    	tables.project_id = allowed_project_id 
	    	AND last_step_was_table_row_ref_next
	    	AND tables.digest = parse_table_row_ref_table_digest(expand_table.data_dump)
	    LEFT JOIN table_rows ON
	    	table_rows.project_id = allowed_project_id
	    	AND table_rows.digest = arrayElement(tables.row_digests, parse_table_row_ref_row_index(expand_table.data_dump) + 1)
	    WHERE LENGTH(expand_table.remaining_path_paths) > 0 OR last_step_was_ref
	)
	SELECT TOP 1 data_dump FROM expand_table ORDER BY iteration DESC
)
