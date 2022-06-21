import {useMemo, useState, useRef, useEffect} from 'react';
import * as CGReact from '@wandb/common/cgreact';
import * as HL from '@wandb/cg/browser/hl';
import * as Types from '@wandb/cg/browser/model/types';
import {useDeepMemo} from '@wandb/common/state/hooks';

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
export const useRefineExpressionsEffect = (
  expressions: Array<Types.NodeOrVoidNode<Types.Type>>,
  frame: {[x: string]: Types.Node}
) => {
  expressions = useDeepMemo(expressions);
  const refineEditingNode = CGReact.useClientBound(HL.refineEditingNode);
  const currentlyRefining = useRef<boolean>(false);
  const currentlyRefiningExpressions = useRef<null | Types.NodeOrVoidNode[]>(
    null
  );
  const expressionsWeRefined = useRef<Types.NodeOrVoidNode[]>([]);
  const [refinedExpressions, setRefinedExpressions] = useState(expressions);

  useEffect(() => {
    if (
      currentlyRefining.current &&
      currentlyRefiningExpressions.current === expressions
    ) {
      return;
    }

    currentlyRefining.current = true;
    currentlyRefiningExpressions.current = expressions;
    Promise.all(expressions.map(exp => refineEditingNode(exp, frame))).then(
      newlyRefinedExpressions => {
        if (currentlyRefiningExpressions.current === expressions) {
          currentlyRefining.current = false;

          // TODO: not sure if any is actually correct here: it smooths over the possibility
          // of void inputs in the refined graphs
          expressionsWeRefined.current = expressions;
          setRefinedExpressions(newlyRefinedExpressions as any);
        }
      }
    );
  }, [expressions, frame, refineEditingNode]);

  return useMemo(() => {
    if (currentlyRefining.current) {
      return {
        isRefining: true,
        refinedExpressions: expressions,
      };
    }
    if (expressionsWeRefined.current === expressions) {
      return {
        isRefining: false,
        refinedExpressions,
      };
    } else {
      // ExpressionEditor refines the expression as the user edits. We pass
      // through the original expression (which has already been refined by the
      // expression editor), unless we've specifically refined it.
      return {
        isRefining: true,
        refinedExpressions: expressions,
      };
    }
  }, [expressions, refinedExpressions]);
};

export const useRefineExpressionEffect = (
  expression: Types.NodeOrVoidNode<Types.Type>,
  frame: {[x: string]: Types.Node}
) => {
  const expressions = useMemo(() => [expression], [expression]);
  const result = useRefineExpressionsEffect(expressions, frame);
  return useMemo(
    () => ({
      ...result,
      refinedExpression: result.refinedExpressions[0],
    }),
    [result]
  );
};
