import {
  makePromiseUsable,
  refineExpression,
  refineExpressions,
} from '../PanelTable/hooks';

// Given an expression, frame, and update callback, asynchronously
// update the expression if needed. This function can be used generally
// for any panel that constructs & maintains an expression in their own
// config. The expected pattern is that the Panel constructs a frame
// using the panel's input nodes and calls this "use" function. The returned
// boolean should act like a "loading" guard and will be `true` when
// the expression is in the async process of refinement. The Panel should
// not load any children panels as the output node is unsafe at that time.
// The refinement will happen on the first load of the Panel - allowing for
// type system / cg updates, as well as any time variables referenced
// by the expression change.

export const useRefineExpressionEffect = makePromiseUsable(refineExpression);
export const useRefineExpressionsEffect = makePromiseUsable(refineExpressions);
