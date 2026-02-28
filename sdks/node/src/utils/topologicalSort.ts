/**
 * Topologically sort node IDs such that children appear before their parents.
 *
 * The algorithm is an iterative BFS (Kahn's variant):
 *   1. Pre-populate a resolved set with every parent ID not present as a key
 *      in the map (external roots: trace IDs, untracked spans, etc.).
 *   2. Find all nodes whose parent is undefined or already in the resolved set.
 *   3. Add them to the resolved set; their in-map children become eligible.
 *   4. Repeat until the remaining set is empty.
 *   4. Reverse the collected levels so deepest nodes come first.
 *
 * If a cycle is detected (no eligible nodes remain but the set is non-empty),
 * the remaining nodes are appended in arbitrary order.
 *
 * @param parentOf - Map from node ID to its parent ID (undefined means no parent).
 *                   Any parentId not present as a key in this map is treated as
 *                   an external root, making the child a root node.
 * @returns Node IDs sorted children-first (deepest descendants before ancestors).
 */
export function topologicalSortChildrenFirst(
  parentOf: Map<string, string | undefined>
): string[] {
  // Pre-populate seen with every parent ID that is not itself a node in the
  // map (external roots: trace IDs, untracked spans, etc.). This means the
  // loop condition never needs a map lookup — a node is ready as soon as its
  // parent is in `seen`.
  const seen = new Set<string>();
  for (const parentId of parentOf.values()) {
    if (parentId !== undefined && !parentOf.has(parentId)) {
      seen.add(parentId);
    }
  }

  const remaining = new Set<string>(parentOf.keys());
  const levels: string[][] = [];

  while (remaining.size > 0) {
    const currentLevel: string[] = [];
    for (const id of remaining) {
      const parentId = parentOf.get(id);
      if (parentId === undefined || seen.has(parentId)) {
        currentLevel.push(id);
      }
    }

    if (currentLevel.length === 0) {
      // Cycle detected — append remaining nodes in arbitrary order.
      levels.push([...remaining]);
      break;
    }

    levels.push(currentLevel);
    for (const id of currentLevel) {
      seen.add(id);
      remaining.delete(id);
    }
  }

  // Reverse so deepest level (children) comes first.
  const result: string[] = [];
  for (let i = levels.length - 1; i >= 0; i--) {
    result.push(...levels[i]);
  }
  return result;
}
