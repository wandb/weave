import json
import sys
from collections import deque
from pathlib import Path
from typing import Any


def find_child_defs(node: dict[str, Any]) -> set[str]:
    """Find all definition references in a node."""
    child_defs = set()

    def collect_refs(n: Any) -> None:
        if isinstance(n, dict):
            if "$ref" in n:
                ref = n["$ref"]
                if ref.startswith("#/$defs/"):
                    child_defs.add(ref[8:])  # Remove "#/$defs/" prefix
            for v in n.values():
                collect_refs(v)
        elif isinstance(n, list):
            for item in n:
                collect_refs(item)

    collect_refs(node)
    return child_defs


def find_path_to_root(schema: dict[str, Any], root_def: str) -> list[str]:
    """
    Find a path from any descendant back to the root definition.
    Returns the path if found, empty list if no path exists.
    """
    queue = deque([(root_def, [root_def])])
    visited = {root_def}

    while queue:
        current_def, path = queue.popleft()

        # Get the definition node
        def_node = schema["$defs"][current_def]

        # Find all child definitions
        child_defs = find_child_defs(def_node)

        for child_def in child_defs:
            if child_def == root_def:
                # Found a path back to root
                return path + [child_def]
            if child_def not in visited:
                visited.add(child_def)
                queue.append((child_def, path + [child_def]))

    return []


def rewrite_circular_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Rewrite circular references in the schema by iteratively finding and breaking cycles.
    For each cycle found, replaces the last reference back to root with 'any'.
    """
    defs = schema.get("$defs", {})

    for root_def in defs:
        while True:
            # Find a path back to root
            path = find_path_to_root(schema, root_def)
            if not path:
                break

            # Get the last node before the cycle
            last_node = schema["$defs"][path[-2]]

            # Replace the reference to root with any
            def process_node(node: Any) -> Any:
                if isinstance(node, dict):
                    if "$ref" in node and node["$ref"] == f"#/$defs/{root_def}":
                        return {"title": root_def}
                    return {k: process_node(v) for k, v in node.items()}
                elif isinstance(node, list):
                    return [process_node(item) for item in node]
                return node

            schema["$defs"][path[-2]] = process_node(last_node)

    return schema


def main():
    if len(sys.argv) != 2:
        print("Usage: python resolve_schema_circular_refs.py <schema_path>")
        sys.exit(1)

    schema_path = Path(sys.argv[1])

    # Read the schema
    with schema_path.open("r") as f:
        schema = json.load(f)

    # Rewrite circular references
    schema = rewrite_circular_refs(schema)

    # Write back the modified schema
    with schema_path.open("w") as f:
        json.dump(schema, f, indent=2)
    print(f"Rewrote circular references in {schema_path}")


if __name__ == "__main__":
    main()
