import {
  EditingNode,
  EditingOutputNode,
  getOpDefsByDisplayName,
  getStackAtNodeOrOp,
  isVarNode,
  isWeaveDebugEnabled,
  maybeReplaceNode,
  Parser,
  resolveVar,
  Stack,
  voidNode,
  WeaveInterface,
} from '@wandb/weave/core';
import {isFunction} from 'lodash';
import {Editor, Node, Path, Point, Range, Text, Transforms} from 'slate';

export const trace = (...args: any[]) => {
  if (isWeaveDebugEnabled()) {
    console.log(...args.map(a => (isFunction(a) ? a() : a)));
  }
};

// Find the most specific node associated with offset,
// working backward until we find a relevant node
export function nodesAtOffset(
  offset: number,
  root: Parser.SyntaxNode,
  nodeMap: Map<number, EditingNode>
): [Parser.SyntaxNode, EditingNode | undefined] {
  if (offset < 0) {
    throw new Error('nothing found');
  }

  let curNode: Parser.SyntaxNode | null = root;
  const nodeStack = [];
  while (curNode != null) {
    nodeStack.push(curNode);
    let foundChild = false;
    // TSC gets type of child wrong here for some reason
    // @ts-ignore
    for (const child of curNode.namedChildren) {
      if (offset >= child.startIndex && offset <= child.endIndex) {
        foundChild = true;
        curNode = child;
        break;
      }
    }
    if (!foundChild) {
      curNode = null;
    }
  }

  for (let node = nodeStack.pop(); node != null; node = nodeStack.pop()) {
    if (node.type === 'ERROR') {
      break;
    }
    const cgNode = nodeMap.get(node.id);
    if (cgNode) {
      return [node, cgNode];
    }
  }

  return nodesAtOffset(offset - 1, root, nodeMap);
}

// Get the Slate Range representing a given tree sitter parse tree node
export function rangeForSyntaxNode(
  tsNode: Parser.SyntaxNode,
  editor: Editor
): Range {
  return {
    anchor: getPointForIndex(editor, tsNode.startIndex),
    focus: getPointForIndex(editor, tsNode.endIndex),
  };
}

// Returns the raw offset of the current or previous selection's end
export function getSelectionIndex(editor: Editor): number {
  let result = 0;

  // Calculate index in raw string from editor selection
  // TODO(np): Fix these types
  const selection: Range = editor.selection ?? Editor.range(editor, []);
  if (selection != null) {
    if (!Point.equals(selection.anchor, selection.focus)) {
      // When anchor != focus, user has something selected
      // console.log(`selection active`);
    }

    // Iterate over all nodes up to anchor path, incrementing rawIndex
    // for every text (leaf) node we find
    const end = Range.end(selection);
    for (const entry of Node.nodes(editor, {
      to: end.path,
    })) {
      const [node, path] = entry;
      if (Path.equals(path, end.path ?? [])) {
        break;
      }
      if (Text.isText(node)) {
        result += (node as Text).text.length;
      }
    }
    result += end.offset;
  }

  return result;
}

// Returns the raw offset of a given Slate Point
export function getIndexForPoint(editor: Editor, point: Point): number {
  let result = 0;

  // Iterate over all nodes up to anchor path, incrementing rawIndex
  // for every text (leaf) node we find
  for (const entry of Node.nodes(editor, {
    to: point.path,
  })) {
    const [node, path] = entry;
    if (Path.equals(path, point.path)) {
      break;
    }
    if (Text.isText(node)) {
      result += (node as Text).text.length;
    }
  }
  result += point.offset;

  return result;
}

// Essentially the inverse of getIndexForPoint.  Given an editor and an index, try to find
// the exact path.  Basically we traverse the slate tree in order
export function getPointForIndex(editor: Editor, index: number): Point {
  let remainingIndex = index;
  for (const entry of Node.nodes(editor)) {
    const [node, path] = entry;
    if (!Text.isText(node)) {
      continue;
    }
    const nodeTextLength = node.text.length;
    if (nodeTextLength >= remainingIndex) {
      return {
        path,
        offset: remainingIndex,
      };
    }
    remainingIndex -= nodeTextLength;
  }

  return Editor.point(editor, [], {edge: 'start'});
}

// Move cursor ahead to likely next missing value or to end
// We search for certain patterns
export function moveToNextMissingArg(editor: Editor) {
  const currentPosition = getSelectionIndex(editor);
  const textAfterCursor = Editor.string(editor, []).slice(currentPosition);

  let nextPos = Infinity;
  for (const pattern of [
    ['()', 1],
    ['[]', 1],
    ['""', 1],
    ['(,', 1],
    ['( ,', 1],
    [',,', 1],
    [', ,', 2],
    [',)', 1],
    [', )', 2],
    ['=> )', 3],
    ['=> row)', 6],
    [/[%*+-/<>=]\s*\)$/, 1],
  ]) {
    const [token, insertPoint] = pattern as [string | RegExp, number];
    const tokenPos =
      typeof token === 'string'
        ? textAfterCursor.indexOf(token)
        : textAfterCursor.match(token)?.index ?? -1;
    if (tokenPos === -1) {
      continue;
    } else {
      const position = tokenPos + insertPoint;
      if (position < nextPos) {
        nextPos = position;
      }
    }
  }

  if (nextPos === Infinity) {
    Transforms.select(editor, Editor.end(editor, []));
  } else {
    Transforms.move(editor, {distance: nextPos, unit: 'offset'});
  }
}

// Centralize some suggestions hacks
export async function adaptSuggestions(
  weave: WeaveInterface,
  targetNode: EditingNode,
  expression: EditingNode,
  stack: Stack,
  extraText?: string
) {
  // console.log(`adaptSuggestions`, targetNode, expression, frame);

  const placeholder = voidNode();

  // HACK: extraText exists when we encounter a parse error.  Try
  // constructing a binary op
  if (extraText) {
    const opDefs = getOpDefsByDisplayName(
      extraText.trim(),
      weave.client.opStore
    ).filter(def => {
      const lhsInputType = def.inputTypes.lhs;
      return (
        lhsInputType != null &&
        weave.typeIsAssignableTo(targetNode.type, def.inputTypes.lhs)
      );
    });
    if (opDefs.length === 1) {
      const editingNode: EditingOutputNode = {
        fromOp: {
          name: opDefs[0].name,
          inputs: {
            lhs: targetNode,
            rhs: placeholder,
          },
        },
        nodeType: 'output',
        type: 'any',
      };
      return weave.suggestions(placeholder, editingNode, stack);
    }
  }

  // HACK: identifiers are parsed as variables, whether they are in scope or not.
  // inspect the frame and use variable if it's in scope, otherwise replace with
  // a void node.
  const activeStack =
    getStackAtNodeOrOp(expression, targetNode, stack, weave.client.opStore) ??
    stack;

  if (
    isVarNode(targetNode) &&
    resolveVar(activeStack, targetNode.varName) == null
  ) {
    return weave.suggestions(
      placeholder,
      maybeReplaceNode(expression, targetNode, placeholder),
      stack,
      targetNode.varName
    );
  }

  return weave.suggestions(targetNode, expression, stack, extraText);
}
