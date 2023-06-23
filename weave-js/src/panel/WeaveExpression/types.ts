export {};
// import type {EditingNode, Stack} from '@wandb/weave/core';
// import type {Node as SlateNode} from 'slate';
//
// export interface SuggestionProps {
//   // For insert position hacks
//   node: EditingNode;
//
//   // To display the type of the node for which we're providing suggestions
//   // null when node is void
//   typeStr: string | null;
//
//   // TODO(np): This is pretty janky.  Suggestions API needs to be updated to better
//   // interoperate w/ the new editing paradigm.
//   items: Array<AutosuggestResult<any>>; // this appears to be recursive? is this really a list of SuggestionProps?
//
//   isBusy: boolean;
//   suggestionIndex?: number;
//
//   forceHidden?: boolean;
//
//   extraText?: string;
// }
//
// interface BaseWeaveExpressionAction {
//   type: string;
// }
//
// interface EditorChangedAction extends BaseWeaveExpressionAction {
//   type: 'editorChanged';
//   newValue: SlateNode[];
//   stack: Stack;
// }
//
// interface ExprChangedAction extends BaseWeaveExpressionAction {
//   type: 'exprChanged';
//   expr: EditingNode;
// }
//
// interface SetExprChangedAction extends BaseWeaveExpressionAction {
//   type: 'setExprChanged';
//   setExpr: (expr: EditingNode) => void;
// }
//
// interface StackChangedAction extends BaseWeaveExpressionAction {
//   type: 'stackChanged';
//   stack: Stack;
// }
//
// interface FlushPendingAction extends BaseWeaveExpressionAction {
//   type: 'flushPendingExpr';
// }
//
// export type WeaveExpressionAction =
//   | EditorChangedAction
//   | ExprChangedAction
//   | SetExprChangedAction
//   | StackChangedAction
//   | FlushPendingAction;
