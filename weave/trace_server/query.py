from sqlglot import exp, parse_one
from sqlglot.errors import ParseError
from sqlglot.expressions import Select


def get_table_mapping(table: str, project_id: str) -> str:
    """Given a table from a user's query, return the SELECT statement that defines it."""
    if table == "calls":
        return f"SELECT * FROM calls_merged WHERE project_id = '{project_id}'"
    if table == "calls_stats":
        return f"SELECT * FROM calls_merged_stats WHERE project_id = '{project_id}'"
    if table == "evaluations":
        return f"SELECT * FROM calls_merged WHERE project_id = '{project_id}' AND op_name LIKE 'weave-trace-internal:///{project_id}/op/Evaluation.evaluate:%'"
    if table == "traces":
        return f"SELECT * FROM calls_merged WHERE project_id = '{project_id}' AND parent_id IS NULL"
    if table == "feedback":
        return f"SELECT * FROM feedback WHERE project_id = '{project_id}'"
    raise ValueError(f"Table {table} is not valid")


JSON_COLUMNS = ("inputs", "output", "attributes", "summary", "payload")


def get_cte_prefix(query: str, project_id: str) -> str:
    """Parse the query to identify all (virtual) tables referenced.

    raises errors for invalid queries or unknown tables.

    Returns the a prefix string for the query that defines the referenced
    tables using Common Table Expressions (CTEs).
    """
    # TODO: Can we avoid double parsing the query?

    try:
        tree = parse_one(query)
    except ParseError as e:
        print(e.errors)
        raise ValueError("Expression is not valid") from e

    if not isinstance(tree, Select):
        raise TypeError("Expression is not a SELECT statement")

    tables = set(tree.find_all(exp.Table))
    ctes = []
    for table in tables:
        mapping = get_table_mapping(table.name, project_id)
        ctes.append(f"{table.name} AS ({mapping})")

    prefix = "WITH " + ",\n".join(ctes)
    return prefix


def prepare_query(query: str, project_id: str, *, pretty: bool = True) -> str:
    """Analyze a SQL query provided by a user and translate it
    into the ClickHouse query we want to execute."""
    prefix = get_cte_prefix(query, project_id)

    try:
        tree = parse_one(query)
    except ParseError as e:
        print(e)
        raise ValueError("Expression is not valid") from e
    if not isinstance(tree, Select):
        raise TypeError("Expression is not a SELECT statement")

    # * will include display_name, which causes problems for some reason I haven't investigated yet
    for star in tree.find_all(exp.Star):
        if isinstance(star.parent, exp.Count):  # Allow COUNT(*)
            continue
        raise ValueError("Star expressions (*) are not supported")


    # TODO: Handle dot and bracket transforms first
    for col in tree.find_all(exp.Column):
        if col.this.name in JSON_COLUMNS:
            col.replace(parse_one(f"{col.this.name}_dump as {col.this.name}"))

    # TODO: Should we check against known columns?

    return prefix + "\n" + tree.sql(dialect="clickhouse", pretty=pretty)
