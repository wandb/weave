import {NodeEntry, Range, Text} from 'slate';
import {getIndexForPoint} from '@wandb/weave/panel/WeaveExpression/util';
import {SyntaxNode} from 'web-tree-sitter';
import {useCallback, useRef} from 'react';
import {useExpressionSuggestionsContext} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';
import {useExpressionEditorContext} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionEditorProvider';

// Provides the decorate callback to pass to Slate's Editable
// component and implements syntax highlighting and styling
// for active node.  The marked ranges are used by Slate to
// emit spans affixed with classes.  See `./styles.ts` for the
// actual CSS rules.
export const usePropsEditableDecorate = () =>
  // rootNode?: SyntaxNode // TODO: confirm this is importing the right thing from the right place
  {
    console.log('run usePropsEditableDecorate');
    const {slateEditor, isEditorFocused} = useExpressionEditorContext();
    // TODO: maybe ranges should be ref not state?
    const ranges = useRef<Range[]>([]);

    const {
      parseResult: {parseTree: rootNode},
    } = useExpressionSuggestionsContext();

    const {activeNodeRange} = slateEditor;
    const pushRange = useCallback(
      (r: Range) => {
        // if (!isEditorFocused || activeNodeRange == null) {
        if (activeNodeRange == null) {
          return;
        }
        // The active node range may lie across several ranges.  Any
        // range that intersects the active node range should be
        // styled active.
        // if (isFocused && activeNodeRange != null) {
        const activeNodeIntersect = Range.intersection(
          activeNodeRange, // as any,
          r
        );
        // if (activeNodeIntersect != null) {
        //   r.ACTIVE_NODE = true;
        // }
        // }
        ranges.current = [
          ...ranges.current,
          {...r, ACTIVE_NODE: activeNodeIntersect != null},
        ];
        // setRanges(prevRanges => [
        //   ...prevRanges,
        //   // TODO: rename ACTIVE_NODE to isActive
        //   {...r, ACTIVE_NODE: activeNodeIntersect != null},
        // ]);
        // ranges.push(r);
      },
      [activeNodeRange]
    );

    const pushRangesForNode = useCallback(
      ({
        parseNode,
        typeStack,
        path,
        baseOffset,
      }: {
        parseNode: SyntaxNode;
        typeStack: string[];
        path: number[];
        baseOffset: number;
      }): void => {
        if (['"', "'", '(', ')', '[', ']', '.'].includes(parseNode.type)) {
          return;
        }

        // Recursively push ranges for this node or its named children.
        if (parseNode.namedChildCount > 0) {
          for (const childNode of parseNode.namedChildren) {
            pushRangesForNode({
              parseNode: childNode,
              typeStack: [...typeStack, parseNode.type],
              path: [...path, childNode.startIndex], // TODO: is this right or is copilot wrong
              baseOffset,
            });
          }
          return;
        }
        // TODO: wtf is going on here
        const typesToApply = Object.fromEntries(
          typeStack.concat(parseNode.type).map(t => [t, true])
        );
        pushRange({
          ...typesToApply,
          anchor: {path, offset: parseNode.startIndex - baseOffset},
          focus: {path, offset: parseNode.endIndex - baseOffset},
        });
      },
      [pushRange]
    );

    // Each line is passed separately, so we pass the parse tree
    // separately and apply some arithmetic to get to the right
    // offset(s)
    // decorate returns an array of ranges with marks applied
    const decorateCallback = useCallback(
      ([node, path]: NodeEntry): Range[] => {
        // const ranges: Range[] = [];

        // const editorIsFocused = ReactEditor.isFocused(editor);
        console.log('run decorateCallback', {
          rootNode,
          slateEditor,
          node,
          path,
        });

        if (rootNode == null || !Text.isText(node)) {
          console.log(
            'decorate: returning empty ranges',
            rootNode == null,
            !Text.isText(node)
          );
          // Can't do highlighting if there's no parse tree and ignore non-text nodes
          // TODO: this should probably return []?
          return ranges.current;
        }

        // baseOffset is relative to the editor's entire contents, not just this node.
        const baseOffset = getIndexForPoint(slateEditor, {path, offset: 0});

        // Starting at the base offset, get the parse node at the cursor position
        // and recursively push ranges for that node and its children.
        for (
          let cursor = baseOffset,
            parseNode = rootNode.namedDescendantForIndex(cursor);
          cursor < baseOffset + node.text.length && parseNode.parent !== null;
          cursor = parseNode.endIndex + 1,
            parseNode = rootNode.namedDescendantForIndex(cursor)
        ) {
          pushRangesForNode({parseNode, typeStack: [], path, baseOffset});
        }

        return ranges.current;
      },
      // [rootNode, slateEditor, ranges, pushRangesForNode]
      // [rootNode, ranges, pushRangesForNode]
        TODO: working on this infinite loop
      [rootNode, slateEditor]
    );

    return decorateCallback;
  };
