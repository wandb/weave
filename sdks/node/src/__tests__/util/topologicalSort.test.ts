import {topologicalSortChildrenFirst} from '../../utils/topologicalSort';

// Helper: assert that every parent appears after all its children in the result.
function assertChildrenBeforeParents(
  result: string[],
  parentOf: Map<string, string | undefined>
) {
  const position = new Map(result.map((id, i) => [id, i]));
  for (const [id, parentId] of parentOf) {
    if (parentId !== undefined && position.has(parentId)) {
      const childPos = position.get(id)!;
      const parentPos = position.get(parentId)!;
      if (childPos >= parentPos) {
        throw new Error(
          `expected ${id} (pos ${childPos}) to come before parent ${parentId} (pos ${parentPos})`
        );
      }
    }
  }
}

describe('topologicalSortChildrenFirst', () => {
  test('empty map returns empty array', () => {
    expect(topologicalSortChildrenFirst(new Map())).toEqual([]);
  });

  test('single node with no parent', () => {
    const parentOf = new Map([['a', undefined]]);
    expect(topologicalSortChildrenFirst(parentOf)).toEqual(['a']);
  });

  test('single node whose parent is an external ID (not in map) is treated as root', () => {
    // e.g. a span whose only parent is a trace ID
    const parentOf = new Map<string, string | undefined>([['a', 'trace-1']]);
    expect(topologicalSortChildrenFirst(parentOf)).toEqual(['a']);
  });

  test('linear chain: deepest child comes first', () => {
    // a → b → c  (a is root, c is leaf)
    const parentOf = new Map<string, string | undefined>([
      ['a', undefined],
      ['b', 'a'],
      ['c', 'b'],
    ]);
    expect(topologicalSortChildrenFirst(parentOf)).toEqual(['c', 'b', 'a']);
  });

  test('linear chain rooted at an external trace ID', () => {
    // trace-1 is not in the map; a is root, b and c are nested below it
    const parentOf = new Map<string, string | undefined>([
      ['a', 'trace-1'],
      ['b', 'a'],
      ['c', 'b'],
    ]);
    expect(topologicalSortChildrenFirst(parentOf)).toEqual(['c', 'b', 'a']);
  });

  test('siblings at the same depth appear before their shared parent', () => {
    // root → left, root → right
    const parentOf = new Map<string, string | undefined>([
      ['root', undefined],
      ['left', 'root'],
      ['right', 'root'],
    ]);
    const result = topologicalSortChildrenFirst(parentOf);
    assertChildrenBeforeParents(result, parentOf);
    expect(result).toHaveLength(3);
    expect(result[result.length - 1]).toBe('root');
  });

  test('multiple independent trees', () => {
    // tree1: a → b   tree2: x → y
    const parentOf = new Map<string, string | undefined>([
      ['a', undefined],
      ['b', 'a'],
      ['x', undefined],
      ['y', 'x'],
    ]);
    const result = topologicalSortChildrenFirst(parentOf);
    assertChildrenBeforeParents(result, parentOf);
    expect(result).toHaveLength(4);
  });

  test('all spans parented to an external trace ID are all roots', () => {
    const parentOf = new Map<string, string | undefined>([
      ['span-1', 'trace-1'],
      ['span-2', 'trace-1'],
      ['span-3', 'trace-1'],
    ]);
    const result = topologicalSortChildrenFirst(parentOf);
    expect(result.sort()).toEqual(['span-1', 'span-2', 'span-3'].sort());
  });

  test('mixed: some spans parented to trace ID, some nested under other spans', () => {
    // span-A and span-C are direct children of external trace-1 (roots)
    // span-B is a child of span-A
    const parentOf = new Map<string, string | undefined>([
      ['span-A', 'trace-1'],
      ['span-B', 'span-A'],
      ['span-C', 'trace-1'],
    ]);
    const result = topologicalSortChildrenFirst(parentOf);
    assertChildrenBeforeParents(result, parentOf);
    expect(result).toHaveLength(3);
    expect(result.indexOf('span-B')).toBeLessThan(result.indexOf('span-A'));
  });

  test('node whose parent is an untracked span (e.g. skipped response span) is treated as root', () => {
    // span-A's parent is a response span not in the map; it must sort as a root.
    // span-B is a child of span-A.
    const parentOf = new Map<string, string | undefined>([
      ['span-A', 'response-span-id'],
      ['span-B', 'span-A'],
    ]);
    const result = topologicalSortChildrenFirst(parentOf);
    expect(result).toEqual(['span-B', 'span-A']);
  });

  test('cycle: remaining nodes are appended rather than hanging', () => {
    // a → b → a  (cycle, no external roots)
    const parentOf = new Map<string, string | undefined>([
      ['a', 'b'],
      ['b', 'a'],
    ]);
    const result = topologicalSortChildrenFirst(parentOf);
    expect(result.sort()).toEqual(['a', 'b']);
  });

  test('cycle mixed with valid nodes: valid nodes sorted correctly, cycle nodes appended', () => {
    // root → child (valid), x → y → x (cycle)
    const parentOf = new Map<string, string | undefined>([
      ['root', undefined],
      ['child', 'root'],
      ['x', 'y'],
      ['y', 'x'],
    ]);
    const result = topologicalSortChildrenFirst(parentOf);
    expect(result.indexOf('child')).toBeLessThan(result.indexOf('root'));
    expect(result).toContain('x');
    expect(result).toContain('y');
    expect(result).toHaveLength(4);
  });
});
