import * as React from 'react';
import {useCallback, useContext, useMemo, useState} from 'react';
import {Icon} from 'semantic-ui-react';
import {createStore} from 'redux';

import {constNumber, constString} from '@wandb/cg/browser/ops';
import * as HL from '@wandb/cg/browser/hl';
import * as CG from '@wandb/cg/browser/graph';
import * as Suggest from '@wandb/cg/browser/suggest';
import * as Types from '@wandb/cg/browser/model/types';
import * as CGTypes from '@wandb/cg/browser/types';
import * as CGParser from '@wandb/cg/browser/parser';
import {toString} from '@wandb/cg/browser/hl';
import {Client} from '@wandb/cg/browser';
import {AutosuggestResult} from '@wandb/cg/browser/suggest';

import {BLOCK_POPUP_CLICKS_CLASSNAME} from '@wandb/common/util/semanticHacks';
import {useDebouncedEffect} from '@wandb/common/util/hooks';
import * as CGReact from '@wandb/common/cgreact';
import {toast} from '@wandb/common/components/elements/Toast';
import LinkButton from '@wandb/common/components/LinkButton';
import * as Panel2 from './panel';
import {ToastIconContainer} from './ExpressionEditor.styles';
import {
  Provider,
  useDispatch,
  useSelector,
  TypedUseSelectorHook,
} from 'react-redux';

export const FrameContext = React.createContext<{
  [argName: string]: Types.Node;
}>({});

interface ExpressionEditorSharedProps {
  node: CGTypes.EditingNode;
  debug?: boolean;
}

interface ExpressionEditorInternalState {
  buffer: string;
  tailOpKey: number;

  // Focus on void, var, or output node means the user is chaining an
  // an op. Focus on a const node means they're editing that const.
  // Focus on an Op means editing an op name.
  focus?: CGTypes.EditingNode | CGTypes.EditingOp;
  cursorPos?: number;

  hover?: CGTypes.EditingNode | CGTypes.EditingOp;

  suggestions: Array<AutosuggestResult<any>>;

  showPlainText: boolean;
  isEditingPlainText: boolean;
  plainTextHasError: boolean;
}

export interface ExpressionEditorReduxState {
  internalState: ExpressionEditorInternalState;
  props: ExpressionEditorSharedProps;
}
export type ExpressionEditorReduxStateUpdate = {
  [key in keyof ExpressionEditorReduxState]?: Partial<
    ExpressionEditorReduxState[key]
  >;
};

type ExpressionEditorReduxAction =
  | {
      type: 'setInternalState';
      payload: Partial<ExpressionEditorInternalState>;
    }
  | {
      type: 'setProps';
      payload: ExpressionEditorSharedProps;
    };

function nodeOrOpToString(
  nodeOrOp: CGTypes.EditingNode | CGTypes.EditingOp,
  graph: CGTypes.EditingNode
) {
  return HL.isEditingNode(nodeOrOp)
    ? `N: ${HL.toString(nodeOrOp, null)}`
    : `Op: ${HL.opToString(nodeOrOp, graph, null)}`;
}

function createEEStore(initialProps: ExpressionEditorSharedProps) {
  return createStore(
    (
      state: ExpressionEditorReduxState | undefined,
      action: ExpressionEditorReduxAction
    ): ExpressionEditorReduxState => {
      if (!state) {
        state = {
          internalState: {
            buffer: '',
            tailOpKey: 0,
            showPlainText: false,
            isEditingPlainText: false,
            plainTextHasError: false,
            suggestions: [],
          },
          props: initialProps,
        };
      }

      switch (action.type) {
        case 'setInternalState':
          return {
            ...state,
            internalState: {
              ...state.internalState,
              ...action.payload,
            },
          };
        case 'setProps':
          return {
            ...state,
            props: action.payload,
          };
        default:
          return state;
      }
    }
  );
}
type EEReduxStore = ReturnType<typeof createEEStore>;
const useEEDispatch = () => useDispatch<EEReduxStore['dispatch']>();
export const useEESelector: TypedUseSelectorHook<ExpressionEditorReduxState> =
  useSelector;

export interface LogContext {
  debug?: boolean;
  origin: string;
  originNodeOrOp?: CGTypes.EditingNode | CGTypes.EditingOp;
  graph: CGTypes.EditingNode;
}
function log(ctx: LogContext, message: string) {
  if (!ctx.debug) {
    return;
  }

  console.groupCollapsed(
    `From: ${ctx.origin}${
      ctx.originNodeOrOp
        ? ` (${nodeOrOpToString(ctx.originNodeOrOp, ctx.graph)})`
        : ''
    }
    ${message}`
  );
  console.trace();
  console.groupEnd();
}

export async function updateNodeAndFocus(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  logContext: LogContext,
  newNodeOrOp: CGTypes.EditingNode | CGTypes.EditingOp,
  forceFocus?: {
    nodeOrOpToFocus: CGTypes.EditingNode | CGTypes.EditingOp;
    initialCursorAtEnd?: boolean;
  }
): Promise<void> {
  log(
    logContext,
    `Replacing current focus (${
      reduxState.internalState.focus
        ? nodeOrOpToString(
            reduxState.internalState.focus,
            reduxState.props.node
          )
        : ''
    }) with new node or op (${nodeOrOpToString(
      newNodeOrOp,
      reduxState.props.node
    )})`
  );
  if (reduxState.internalState.focus == null) {
    throw new Error('Invalid state: focus is null');
  }

  let newGraph: CGTypes.EditingNode<Types.Type>;
  let inferredFocus: CGTypes.EditingNode | CGTypes.EditingOp;
  if (HL.isEditingOp(newNodeOrOp)) {
    // the replacement is an Op

    if (HL.isEditingNode(reduxState.internalState.focus)) {
      throw new Error(
        `Can't replace node ${toString(
          reduxState.internalState.focus
        )} with op ${HL.opToString(newNodeOrOp, reduxState.props.node)}`
      );
    }

    newGraph = HL.replaceOp(
      reduxState.props.node,
      reduxState.internalState.focus,
      newNodeOrOp
    );

    // TODO: assertion that op replace didn't change type

    inferredFocus = newNodeOrOp;

    setReduxState({
      ...reduxState,
      props: {node: newGraph},
      internalState: {focus: inferredFocus},
    });
    return;
  }

  // the replacement is a Node

  if (HL.isEditingOp(reduxState.internalState.focus)) {
    throw new Error(
      `Can't replace op ${reduxState.internalState.focus.name} with node ${newNodeOrOp}`
    );
  }
  if (newNodeOrOp.nodeType === 'void') {
    throw new Error('Expression editor Error: cannot replace with void node');
  }

  // First improve the node if we can
  if (newNodeOrOp.nodeType === 'output') {
    newNodeOrOp = await HL.refineEditingNode(client, newNodeOrOp, frame);
  }

  newGraph = await HL.replaceNodeAndUpdateDownstreamTypes(
    client,
    reduxState.props.node,
    reduxState.internalState.focus,
    newNodeOrOp,
    frame
  );

  inferredFocus = newNodeOrOp;
  if (newNodeOrOp.nodeType === 'output') {
    const inputs = Object.values(newNodeOrOp.fromOp.inputs);

    for (const input of inputs) {
      if (HL.isFunctionLiteral(input) && CG.isVoidNode(input.val)) {
        inferredFocus = input.val;
        break;
      } else if (input.nodeType === 'void') {
        inferredFocus = input;
        break;
      }
    }
  } else if (
    HL.isFunctionLiteral(newNodeOrOp) &&
    CG.isVoidNode(newNodeOrOp.val)
  ) {
    inferredFocus = newNodeOrOp.val;
  }

  // if the newly inserted node is (or contains) an empty string literal,
  // the user probably wanted to edit it, so we'll focus it
  //
  // WARNING: this could create some odd behavior if we implement suggestions
  // that have empty strings in them we don't mean to edit. Parenthesization
  // suggestions seems like a place this might happen, say if the user already
  // had an empty string in the expression they're reparenthesizing
  if (inferredFocus === newNodeOrOp) {
    const emptyStringLiteral = HL.filterNodes(
      newNodeOrOp,
      node => node.nodeType === 'const' && node.val === ''
    );
    if (emptyStringLiteral.length > 0) {
      setReduxState({
        ...reduxState,
        props: {node: newGraph},
        internalState: {focus: emptyStringLiteral[0]},
      });
      return;
    }
  }

  if (inferredFocus === newNodeOrOp) {
    while (inferredFocus !== newGraph) {
      const consumer = HL.findConsumingOp(inferredFocus, newGraph);
      if (consumer == null) {
        // No more downstream nodes to check
        break;
      }
      if (consumer != null) {
        const opDef = CG.getOpDef(consumer.outputNode.fromOp.name);
        const consumerOutputNode = consumer.outputNode;
        const argNames = Object.keys(consumer.outputNode.fromOp.inputs);
        const argNodes = Object.values(consumer.outputNode.fromOp.inputs);
        const argIndex = argNames.indexOf(consumer.argName);
        if (argIndex === -1) {
          throw new Error(
            'Invalid Expression Editor state: invalid consumer value'
          );
        }
        const voidIndex =
          // manyX is the weird array op that takes multiple parameters, just ignore it for now.
          opDef.inputTypes.manyX != null
            ? -1
            : argNodes.findIndex(
                (n, i) =>
                  i >= argIndex &&
                  (n.nodeType === 'void' ||
                    !Types.isAssignableTo(
                      n.type,
                      opDef.inputTypes[argNames[i]]
                    ))
              );
        if (voidIndex !== -1) {
          inferredFocus = argNodes[voidIndex];
          break;
        }
        inferredFocus = consumerOutputNode;
      }
    }
  }

  setReduxState({
    ...reduxState,
    props: {node: newGraph},
    internalState: {
      focus: forceFocus != null ? forceFocus.nodeOrOpToFocus : inferredFocus,
      cursorPos: forceFocus?.initialCursorAtEnd
        ? -1
        : reduxState.internalState.cursorPos,
      buffer: '',
    },
  });
}

export async function updateNode(
  context: Client,
  frame: {
    [argName: string]: Types.Node;
  },
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  node: CGTypes.EditingNode,
  newNodeOrOp: CGTypes.EditingNode
): Promise<void> {
  let newGraph: CGTypes.EditingNode<Types.Type>;
  newGraph = await HL.replaceNodeAndUpdateDownstreamTypes(
    context,
    reduxState.props.node,
    node,
    newNodeOrOp,
    frame
  );

  setReduxState({
    ...reduxState,
    props: {node: newGraph},
    internalState: {suggestions: []},
  });
}

export async function updateConstFunctionNode(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  constFunctionNode: CGTypes.EditingNode,
  replacementFunctionNode: CGTypes.EditingNode
): Promise<void> {
  // If the user picked an op that returns a function, then we
  // can just use replacementFunctionNode directly, its now an
  // output node that gives us our function argument.
  // Otherwise, the user has constructed a new function, keep it
  // as a const node.
  const newNode = Types.isFunction(replacementFunctionNode.type)
    ? replacementFunctionNode
    : {
        ...constFunctionNode,
        val: replacementFunctionNode,
      };
  const newGraph = await HL.replaceNodeAndUpdateDownstreamTypes(
    client,
    reduxState.props.node,
    constFunctionNode,
    newNode,
    frame
  );

  setReduxState({
    ...reduxState,
    props: {node: newGraph},
  });
}

export async function focusOnTail(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void
): Promise<void> {
  setReduxState({
    ...reduxState,
    internalState: {focus: reduxState.props.node},
  });
}

export async function focusNodeOrOp(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  logContext: LogContext,
  nodeOrOp: CGTypes.EditingNode | CGTypes.EditingOp,
  initialCursorAtEnd: boolean = false,
  initialBuffer?: string
) {
  log(
    logContext,
    `focusing (${nodeOrOpToString(nodeOrOp, reduxState.props.node)})`
  );
  if (
    reduxState.internalState.focus !== nodeOrOp ||
    (initialBuffer !== undefined &&
      initialBuffer !== reduxState.internalState.buffer)
  ) {
    log(logContext, 'setting state');
    setReduxState({
      ...reduxState,
      internalState: {
        focus: nodeOrOp,
        cursorPos: initialCursorAtEnd ? -1 : undefined,
        buffer: initialBuffer ?? reduxState.internalState.buffer,
        hover: undefined,
      },
    });
  }
}

export async function blurNodeOrOp(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  logContext: LogContext,
  nodeOrOp: CGTypes.EditingNode | CGTypes.EditingOp
) {
  log(logContext, 'blurring');
  if (reduxState.internalState.focus === nodeOrOp) {
    log(logContext, 'setting state');
    setReduxState({
      ...reduxState,
      internalState: {focus: undefined, buffer: '', hover: undefined},
    });
  }
}

export async function hoverNodeOrOp(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  logContext: LogContext,
  nodeOrOp: CGTypes.EditingNode | CGTypes.EditingOp
) {
  log(logContext, 'hovering');
  if (reduxState.internalState.hover !== nodeOrOp) {
    log(logContext, 'setting state');
    setReduxState({
      ...reduxState,
      internalState: {hover: nodeOrOp},
    });
  }
}

export async function unhoverNodeOrOp(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  logContext: LogContext,
  nodeOrOp: CGTypes.EditingNode | CGTypes.EditingOp
) {
  log(logContext, 'unhovering');
  if (reduxState.internalState.hover === nodeOrOp) {
    log(logContext, 'setting state');
    setReduxState({
      ...reduxState,
      internalState: {hover: undefined},
    });
  }
}

export async function deletePrev(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  logContext: LogContext
): Promise<void> {
  log(logContext, `Deleting in ${HL.toString(reduxState.props.node, null)}`);
  if (
    reduxState.internalState.focus == null ||
    (reduxState.internalState.focus === reduxState.props.node &&
      reduxState.props.node.nodeType === 'void') || // this is the "trying to delete an empty expression" case
    HL.isEditingOp(reduxState.internalState.focus)
  ) {
    // TODO: figure out delete-on-focused op
    // right now, we delete ops by focusing args to the op and deleting those,
    // then deleting again on voided args (see below).

    // but since we're making ops focusable now, we'll need to cover this case.
    // might be as simple as running deletePrev as if one of the args is focused,
    // but should think it through.
    return;
  }

  // in the next block, we'll generate a version of the expression where
  // we've performed a deletion (updatedNode) and select the node that
  // should be focused in the editor after deletion is complete (nextFocus)
  let updatedNode = reduxState.props.node;
  let nextFocus = reduxState.internalState.focus;

  // We keep track of whether we've replaced a node in the graph with
  // void, because we need to refine in that case.
  let replacedANodeWithVoid = false;
  const replaceNode = (
    toReplace: CGTypes.EditingNode,
    replaceWith: CGTypes.EditingNode
  ) => {
    updatedNode = HL.replaceNode(reduxState.props.node, toReplace, replaceWith);
    if (replaceWith.nodeType === 'void') {
      replacedANodeWithVoid = true;
    }
  };

  const rightMostAncestor = HL.rightMostToDelete(nextFocus);
  const {argIndex, outputNode} =
    HL.findConsumingOp(rightMostAncestor, reduxState.props.node) || {};

  // which delete behavior we should use depends on what our consumer is,
  // and where we fall in its list of arguments
  if (
    nextFocus.nodeType === 'output' &&
    ((HL.isDotChainedOp(nextFocus.fromOp) &&
      Object.keys(nextFocus.fromOp.inputs).length === 1) ||
      Panel2.isPanelOpName(nextFocus.fromOp.name))
  ) {
    // Special case for chained unary op (takes no args inside ()).
    // Delete the whole op.

    nextFocus = Object.values(nextFocus.fromOp.inputs)[0];
    replaceNode(reduxState.internalState.focus, nextFocus);
  } else if (outputNode == null || argIndex == null) {
    // we have no consumer: focus is the root node of the expression or of a function
    // literal's body
    if (
      rightMostAncestor.nodeType === 'void' &&
      rightMostAncestor !== reduxState.props.node
    ) {
      // we aren't the root of the entire expression, but we have no op consumer:
      // this means we're the root of a function literal.

      // we'll need to find the function we're a part of, and delete that
      const functionNodes = HL.filterNodes(
        reduxState.props.node,
        node => HL.isFunctionLiteral(node) && node.val === rightMostAncestor
      );

      if (functionNodes.length === 0) {
        throw new Error(
          `Can't find void node that should be root of function literal in expression ${reduxState.props.node}`
        );
      }

      if (functionNodes.length > 1) {
        throw new Error(
          `void node was the root of more than one function literal in expression ${reduxState.props.node}`
        );
      }

      nextFocus = CG.voidNode();
      replaceNode(functionNodes[0], nextFocus);
    } else if (rightMostAncestor.nodeType === 'output') {
      // we should try to delete the rightmost component of the output node at the
      // root.
      const args = Object.values(rightMostAncestor.fromOp.inputs);

      if (args.length === 0) {
        // no args -- presumably a function that takes nothing
        // can be deleted
        // e.g. foo() -> _
        nextFocus = CG.voidNode();
      }

      const first = args[0];
      const rest = args.slice(1);

      let firstNonVoid: CGTypes.EditingNode | undefined;

      for (let i = rest.length - 1; i >= 0; i--) {
        const argNode = rest[i];
        if (argNode.nodeType !== 'void') {
          firstNonVoid = argNode;
          break;
        }
      }

      if (firstNonVoid) {
        // there is a non-void arg within the tail op -- we can delete it
        // e.g. foo(3, x) -> foo(3, _)
        // e.g. x.foo(3, y) -> x.foo(3, _)
        nextFocus = CG.voidNode();
        replaceNode(firstNonVoid, nextFocus);
      } else {
        // all args not in the first position are void -- the first may or may not also
        // be void; it doesn't really matter: at this point we want to replace the op
        // with its (potentially void) first argument
        // e.g. x + _ -> x
        // e.g. x.foo() -> x
        // e.g. x[] -> x
        nextFocus = first;
        replaceNode(rightMostAncestor, nextFocus);
      }
    } else {
      // all non-output nodes in the root position can be deleted directly
      // e.g. 3 -> _
      // e.g. x -> _
      nextFocus = CG.voidNode();
      replaceNode(rightMostAncestor, nextFocus);
    }
  } else {
    const argNodes = Object.values(outputNode.fromOp.inputs);

    if (HL.isBinaryOp(outputNode.fromOp)) {
      // our consumer is a binary infix operator
      if (argIndex === 1) {
        // we're the right child
        if (nextFocus.nodeType !== 'void') {
          // we're NOT already void, so void us out
          // e.g. 3 + 4 -> 3 + _
          nextFocus = CG.voidNode();
          replaceNode(rightMostAncestor, nextFocus);
        } else {
          // replace the binary operator with the left child
          // e.g. 3 + 4 -> 3
          nextFocus = argNodes[0];
          replaceNode(outputNode, nextFocus);
        }
      } else {
        // we're the left child
        if (nextFocus.nodeType !== 'void') {
          // we're NOT already void, so void us out
          // e.g. 3 + 4 -> _ + 4
          nextFocus = CG.voidNode();
          replaceNode(rightMostAncestor, nextFocus);
        } else {
          // we are already void, so delete the entire binary operator
          // e.g. _ + 4 -> _
          nextFocus = CG.voidNode();
          replaceNode(outputNode, nextFocus);
        }
      }
    } else if (HL.isBracketsOp(outputNode.fromOp)) {
      // our consumer is pick (x["foo"]) or index (x[1])
      // these are special cases.
      // regardless of which argument we are, erase the entire op
      // e.g. x["foo"] -> _

      if (outputNode.fromOp.name === 'pick') {
        nextFocus = outputNode.fromOp.inputs.obj;
      } else {
        nextFocus = outputNode.fromOp.inputs.arr;
      }
      replaceNode(outputNode, nextFocus);
    } else if (HL.isDotChainedOp(outputNode.fromOp)) {
      // our consumer is a chained unary operator (x.foo(a,b))

      if (
        argIndex === 0 ||
        (argIndex === 1 && rightMostAncestor.nodeType === 'void')
      ) {
        // we are the first argument (the thing on which we're chaining),
        // OR, we're the first thing inside the parens and we've already been deleted
        // either way: that means we're trying to delete this link off the chain
        // replace us with the thing we chained off of
        // e.g. x.foo() -> x
        // e.g. x.foo(_, 3) -> x (where the cursor is at the _)
        nextFocus = argNodes[0];
        replaceNode(outputNode, nextFocus);
      } else {
        // we're not the first argument (so, we're something inside the parens)
        // delete us
        // e.g. x.foo(1, 2) -> x.foo(1, _)
        // e.g. x.foo(1) -> x.foo(_)
        nextFocus = CG.voidNode();
        replaceNode(rightMostAncestor, nextFocus);

        if (argIndex > 1) {
          // we're not the first thing inside the parentheses, so move the cursor
          // one arg to the left.

          // to see the intention, consider:
          // x.foo(1, 2)
          // if you delete the 2, you should end up focused on the 1 -- but
          // if you delete the 1, you should STAY focused on where the 1 used
          // to be until you delete again and kill the whole chaining
          // operator.

          // this way, if you change your mind -- decide to add the 1 back in --
          // you'll be able to type and replace the thing you just got rid of.
          // if we moved the focus to arg 0, you'd be outside the parens and would
          // have to navigate back in
          nextFocus = argNodes[argIndex - 1];
        }
      }
    } else {
      // our consumer is a function call

      if (argIndex !== 0 || rightMostAncestor.nodeType !== 'void') {
        // either we're not the first argument, OR
        // we're the first argument and we're non void,
        // delete us
        // e.g. function(3, 2) -> function(3, _) -> function(_, _)
        nextFocus = CG.voidNode();
        replaceNode(rightMostAncestor, nextFocus);

        if (argIndex > 0) {
          // same as in unary operator branch above; shift one to the left
          nextFocus = argNodes[argIndex - 1];
        }
      } else {
        // we're the first argument AND already void
        // delete the function call operation
        // e.g. function(_, _) -> _
        nextFocus = CG.voidNode();
        replaceNode(outputNode, nextFocus);
      }
    }
  }
  // Kind of a crazy hack, but works. We need to refine if we've swapped something
  // to a void, so that voids propagate through and invalidate the expression.
  // We don't refine all the time because refine changes all the nodes in the graph
  // and breaks our focus reference. However, refine leaves void nodes alone, so
  // it works in the case we need it to.
  if (replacedANodeWithVoid) {
    updatedNode = await HL.refineEditingNode(client, updatedNode, frame);
  }

  setReduxState({
    ...reduxState,
    props: {node: updatedNode},
    internalState: {focus: nextFocus},
  });
}

export async function setBuffer(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  newBuffer: string
) {
  if (
    !reduxState.internalState.focus ||
    HL.isEditingOp(reduxState.internalState.focus)
  ) {
    setReduxState({...reduxState, internalState: {buffer: newBuffer}});
    return;
  }
  let newTail = reduxState.props.node;
  let newFocus = reduxState.internalState.focus;
  let cursorPos: number | undefined;
  const consumer = HL.findConsumingOp(
    reduxState.internalState.focus,
    reduxState.props.node
  );
  if (consumer != null) {
    const opDef = CG.getOpDef(consumer.outputNode.fromOp.name);
    const argType = opDef.inputTypes[consumer.argName];
    const isNumberArg = Types.isAssignableTo('number', argType);
    const isStringArg = Types.isAssignableTo('string', argType);

    if (reduxState.internalState.focus.nodeType === 'void' && isNumberArg) {
      // Swap to a const number node if the user types or pastes a number
      const matchNum = newBuffer.match(/^\d+/);
      if (matchNum != null) {
        const newConstNode = constNumber(parseFloat(matchNum[0]));
        newTail = await HL.refineEditingNode(
          client,
          HL.replaceNode(
            reduxState.props.node,
            reduxState.internalState.focus,
            newConstNode
          ),
          frame
        );
        newFocus = newConstNode;
        // Move cursor to end of number. (Pasted numbers can have length > 1)
        cursorPos = ('' + matchNum[0]).length;
      }
    } else if (
      reduxState.internalState.focus.nodeType === 'const' &&
      isNumberArg
    ) {
      if (newBuffer === '') {
        // Swap back to a void node if user deletes a number node
        const newVoidNode = CG.voidNode();
        newTail = await HL.refineEditingNode(
          client,
          HL.replaceNode(
            reduxState.props.node,
            reduxState.internalState.focus,
            newVoidNode
          ),
          frame
        );
        newFocus = newVoidNode;
      } else {
        const parsed = Number.parseFloat(newBuffer);

        if (
          !Number.isNaN(parsed) &&
          parsed !== reduxState.internalState.focus.val
        ) {
          // eagerly update the value of a number node whenever the user enters
          // a valid number
          newFocus = {
            ...reduxState.internalState.focus,
            val: parsed,
          };
          newTail = HL.replaceNode(
            reduxState.props.node,
            reduxState.internalState.focus,
            newFocus
          );
        }
      }
    } else if (
      reduxState.internalState.focus.nodeType === 'const' &&
      isStringArg
    ) {
      newFocus = {
        ...reduxState.internalState.focus,
        val: newBuffer,
      };
      newTail = HL.replaceNode(
        reduxState.props.node,
        reduxState.internalState.focus,
        newFocus
      );
    }
  }

  setReduxState({
    ...reduxState,
    props: {node: newTail},
    internalState: {focus: newFocus, buffer: newBuffer, cursorPos},
  });
}

export async function toggleShowPlainText(
  context: Client,
  frame: {
    [argName: string]: Types.Node;
  },
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void
) {
  if (reduxState.internalState.showPlainText) {
    setReduxState({
      ...reduxState,
      internalState: {showPlainText: false, isEditingPlainText: false},
    });
  } else {
    setReduxState({
      ...reduxState,
      internalState: {showPlainText: true},
    });
  }
}

export async function setIsEditingPlainText(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  isEditingPlainText: boolean
) {
  if (reduxState.internalState.isEditingPlainText && !isEditingPlainText) {
    setReduxState({
      ...reduxState,
      internalState: {isEditingPlainText: false},
    });
  } else {
    const parsed = await CGParser.parseCG(
      client,
      toString(reduxState.props.node, null),
      frame
    );
    const plainTextHasError = !!(
      !parsed || !HL.allVarsWillResolve(parsed, frame)
    );
    setReduxState({
      ...reduxState,
      internalState: {isEditingPlainText, plainTextHasError},
    });
  }
}

export async function setPlainTextExpression(
  client: Client,
  frame: {[argName: string]: Types.Node},
  reduxState: ExpressionEditorReduxState,
  setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
  plainTextExpression: string
) {
  const parsed = await CGParser.parseCG(client, plainTextExpression, frame);

  if (parsed) {
    const node = await HL.refineEditingNode(client, parsed, frame);
    const plainTextHasError = !node || !HL.allVarsWillResolve(node, frame);
    setReduxState({
      ...reduxState,
      props: {node},
      internalState: {plainTextHasError},
    });
  } else {
    setReduxState({...reduxState, internalState: {plainTextHasError: true}});
  }
}

interface EEContextState {
  error: any;
  setReduxState(newState: ExpressionEditorReduxState): void;
  setError(newError: any): void;
}

const EEContext = React.createContext<EEContextState | undefined>(undefined);

export const EEContextProvider: React.FC<{
  node: CGTypes.EditingNode;
  frame?: {[argName: string]: Types.Node};
  debug?: boolean;
  updateNode(newNode: CGTypes.EditingNode): void;
}> = props => {
  const store = React.useRef(
    createEEStore({
      node: props.node,
      debug: props.debug,
    })
  );
  return (
    <Provider store={store.current}>
      <FrameContext.Provider value={props.frame || {}}>
        <InnerEEContextProvider {...props} />
      </FrameContext.Provider>
    </Provider>
  );
};

export const InnerEEContextProvider: React.FC<{
  node: CGTypes.EditingNode;
  frame?: {[argName: string]: Types.Node};
  debug?: boolean;
  updateNode(newNode: CGTypes.EditingNode): void;
}> = ({node, frame, debug, updateNode: propUpdateNode, children}) => {
  const [error, setError] = useState();
  const dispatch = useEEDispatch();
  const setInternalState = useCallback(
    (newState: Partial<ExpressionEditorInternalState>) =>
      dispatch({
        type: 'setInternalState',
        payload: newState,
      }),
    [dispatch]
  );

  const setPropsInRedux = useCallback(
    (newProps: ExpressionEditorSharedProps) =>
      dispatch({
        type: 'setProps',
        payload: newProps,
      }),
    [dispatch]
  );
  React.useEffect(() => {
    setPropsInRedux({
      node,
      debug,
    });
  }, [node, frame, debug, setPropsInRedux]);

  // the ref prevents the callback from being recreated when node changes --
  // it only matters what node's value is when the callback is invoked
  const lastNode = React.useRef<ExpressionEditorSharedProps['node']>(node);
  React.useEffect(() => {
    lastNode.current = node;
  }, [node]);
  const setReduxStateAndUpdateNode = useCallback(
    (newState: ExpressionEditorReduxState) => {
      const {internalState: newInternalState} = newState;

      if (newState.props.node !== lastNode.current) {
        propUpdateNode(newState.props.node as any);
      }

      setInternalState(newInternalState);
    },
    [setInternalState, propUpdateNode]
  );

  const autosuggest = CGReact.useClientBound(Suggest.autosuggest);
  const {focus, buffer} = useEESelector(state => ({
    focus: state.internalState.focus,
    buffer: state.internalState.buffer,
  }));
  const autosuggestArgs = useMemo<Parameters<typeof autosuggest> | null>(
    () =>
      frame && focus
        ? ([focus, node, frame, buffer] as Parameters<typeof autosuggest>)
        : null,
    [frame, focus, node, buffer, autosuggest]
  );
  const mostRecentAutosuggestArgs = React.useRef<Parameters<
    typeof autosuggest
  > | null>(autosuggestArgs);

  useDebouncedEffect(
    () => {
      setInternalState({
        suggestions: [],
      });

      if (autosuggestArgs) {
        mostRecentAutosuggestArgs.current = autosuggestArgs;
        autosuggest(...autosuggestArgs).then(newSuggestions => {
          if (mostRecentAutosuggestArgs.current !== autosuggestArgs) {
            // it's possible that looking up the suggestions took so long that
            // the user has already changed the state by the time they come back.
            // In that case, just discard the suggestions
            return;
          }

          setInternalState({
            suggestions: newSuggestions,
          });
          mostRecentAutosuggestArgs.current = null;
        });
      }
    },
    [setInternalState, autosuggestArgs, autosuggest],
    75
  );

  React.useEffect(() => {
    if (error != null) {
      // Throw error in render thread so it can be caught by react error boundaries
      console.error('ExpressionEditorReduxState error', error);
      throw new Error(error);
    }
  }, [error]);

  const contextValue = useMemo<EEContextState>(
    () => ({
      error,
      setError,
      setReduxState: setReduxStateAndUpdateNode,
    }),
    [error, setReduxStateAndUpdateNode]
  );

  return (
    <EEContext.Provider value={contextValue}> {children} </EEContext.Provider>
  );
};

export const useAction = <T extends any[], R>(
  fn: (
    client: Client,
    frame: {[argName: string]: Types.Node},
    reduxState: ExpressionEditorReduxState,
    setReduxState: (newState: ExpressionEditorReduxStateUpdate) => void,
    ...rest: T
  ) => R
): ((...args: T) => R) => {
  const fnWithCGContext = CGReact.useClientBound(fn as any);
  const context = useContext(EEContext);
  if (context == null) {
    throw new Error('EE context not initialized');
  }
  const {setReduxState, setError} = context;
  const reduxState = useEESelector(state => state);

  // using this ref prevents the callback from being recreated when the state
  // changes
  const lastReduxState = React.useRef<ExpressionEditorReduxState>(reduxState);
  React.useEffect(() => {
    lastReduxState.current = reduxState;
  }, [reduxState]);

  const frame = useFrame();

  return useCallback(
    (...args: T) => {
      Promise.resolve(
        fnWithCGContext(frame, lastReduxState.current, setReduxState, ...args)
      ).catch((e: any) => setError(e));
    },
    [fnWithCGContext, frame, setReduxState, setError]
  ) as any;
};

export const useFocusedNodeOrOp = () => {
  return useEESelector(state => state.internalState.focus);
};

export const useHoveredNodeOrOp = () => {
  return useEESelector(state => state.internalState.hover);
};

export const useCursorPos = () => {
  return useEESelector(state => state.internalState.cursorPos);
};

export const useTailNode = () => {
  return useEESelector(state => state.props.node);
};

export const useTailOpKey = () => {
  return useEESelector(state => state.internalState.tailOpKey);
};

export const useBuffer = () => {
  return useEESelector(state => state.internalState.buffer);
};

export const useFrame = () => {
  return useContext(FrameContext);
};

export const useConsumingOp = (node: Types.Node) => {
  return HL.findConsumingOp(
    node,
    useEESelector(state => state.props.node)
  );
};

export const useSuggestions = () => {
  return useEESelector(state => state.internalState.suggestions);
};

export const useShowPlainText = () => {
  return useEESelector(state => state.internalState.showPlainText);
};

export const useIsEditingPlainText = () => {
  return useEESelector(state => state.internalState.isEditingPlainText);
};

export const usePlainTextHasError = () => {
  return useEESelector(state => state.internalState.plainTextHasError);
};

export const useDebug = () => {
  return useEESelector(state => state.props.debug);
};

// only works within a single text node:
const setCursorPosition = (toEnd: boolean) => {
  const selection = window.getSelection();

  if (
    !selection ||
    !selection?.anchorNode ||
    !selection?.anchorNode?.textContent
  ) {
    return;
  }

  const range = document.createRange();
  range.setStart(
    selection.anchorNode,
    toEnd ? selection.anchorNode.textContent.length : 0
  );
  range.collapse(true);

  selection.removeAllRanges();
  selection.addRange(range);
};

export const useHandleEditorKeys = (
  allowSpaces: boolean,
  getLogContext: (origin: string) => LogContext
) => {
  const toggleShowPlainTextAction = useAction(toggleShowPlainText);
  const focusNodeOrOpAction = useAction(focusNodeOrOp);
  const deletePrevAction = useAction(deletePrev);
  const {tailNode, suggestions, buffer, focusedNodeOrOp} = useEESelector(
    state => ({
      tailNode: state.props.node,
      suggestions: state.internalState.suggestions,
      buffer: state.internalState.buffer,
      focusedNodeOrOp: state.internalState.focus,
    })
  );
  const updateNodeAndFocusAction = useAction(updateNodeAndFocus);

  return async (e: React.KeyboardEvent<Element>) => {
    if (e.code === 'Backspace') {
      // When EE has focus, we never allow backspace to propagate because
      // this could delete the panel
      e.stopPropagation();
    }

    const selection = window.getSelection();
    const cursorAtBeginning = selection?.anchorOffset === 0;
    const cursorAtEnd =
      selection?.anchorOffset === selection?.anchorNode?.textContent?.length;

    // Shortcut: Shift+Enter switches to plain text mode
    if (e.code === 'Enter' && e.shiftKey) {
      e.preventDefault();
      e.stopPropagation();
      toggleShowPlainTextAction();
      return;
    }

    if ([57, 48].includes(e.keyCode) && e.shiftKey) {
      e.preventDefault();
      e.stopPropagation();
      toast(
        <span className={BLOCK_POPUP_CLICKS_CLASSNAME}>
          To edit parentheses, switch to{' '}
          <LinkButton onClick={toggleShowPlainTextAction}>
            Plain Text View{' '}
            <ToastIconContainer>
              <Icon name="i cursor" size="small" style={{margin: 0}} />
            </ToastIconContainer>
          </LinkButton>{' '}
          .
        </span>
      );
    }

    if (!allowSpaces && e.key === ' ' && focusedNodeOrOp) {
      // in most editors (string literals are an exception) we don't want to
      // insert spaces...
      e.preventDefault();

      if (cursorAtEnd) {
        // ...but if the user types a space at the end of the input, we should
        // interpret that as a signal to move forward.

        // TODO: this behavior is fine for the end of the expression because it
        // allows the user to add a new binary op -- but it's probably not what
        // the user wants INSIDE the expression. In other words, feels good for
        // a space at the end of:
        //
        // x + 4
        //
        // but bad for a space at the 3 in:
        //
        // x[3] + 4
        //
        // in the latter case, the user probably wanted to keep changing the
        // sub-expression within the brackets, but we move them outside instead.
        // Solving this will require "inserting" nodes from a non-OutputNode.

        const matchingSuggestions = suggestions.filter(
          sugg => sugg.suggestionString.trim() === buffer
        );
        if (matchingSuggestions.length > 0) {
          e.preventDefault();
          updateNodeAndFocusAction(
            getLogContext('space to accept suggestion from void node'),
            matchingSuggestions[0].newNodeOrOp
          );
          return;
        }

        const nextNodeOrOp = HL.getNextNodeOrOpInTextOrder(
          focusedNodeOrOp,
          tailNode
        );

        if (!nextNodeOrOp) {
          // this is the end, we can't go forward
          return;
        }

        e.preventDefault();
        focusNodeOrOpAction(
          getLogContext('space to next'),
          nextNodeOrOp,
          undefined,
          undefined
        );
        return;
      }
    }

    if (e.key === 'ArrowLeft' && focusedNodeOrOp) {
      // jump between nodes
      if (e.metaKey) {
        // jump to the beginning of the expression (cmd + left)
        e.preventDefault();
        const ordered = HL.textOrderedNodesAndOps(tailNode);

        if (focusedNodeOrOp === ordered[0]) {
          setCursorPosition(false);
        } else {
          focusNodeOrOpAction(
            getLogContext('command-left to beginning'),
            ordered[0]
          );
        }
        return;
      } else if (cursorAtBeginning) {
        const prevNodeOrOp = HL.getPrevNodeOrOpInTextOrder(
          focusedNodeOrOp,
          tailNode
        );

        if (!prevNodeOrOp) {
          // this is the beginning, we can't go back any further
          return;
        }

        e.preventDefault();
        focusNodeOrOpAction(
          getLogContext('left arrow to prev'),
          prevNodeOrOp,
          true,
          undefined
        );
        return;
      }
    }

    if (e.key === 'ArrowRight' && focusedNodeOrOp) {
      if (e.metaKey) {
        // jump to the end of the expression (cmd + right)
        e.preventDefault();

        if (focusedNodeOrOp === tailNode) {
          setCursorPosition(true);
        } else {
          focusNodeOrOpAction(
            getLogContext('cmd-right to end'),
            tailNode,
            true
          );
        }
        return;
      } else if (cursorAtEnd) {
        // jump to the next node
        const nextNodeOrOp = HL.getNextNodeOrOpInTextOrder(
          focusedNodeOrOp,
          tailNode
        );

        if (!nextNodeOrOp) {
          // this is the end, we can't go forward
          return;
        }

        e.preventDefault();
        focusNodeOrOpAction(
          getLogContext('right arrow to next'),
          nextNodeOrOp,
          undefined,
          undefined
        );
        return;
      }
    }

    // handle automatically switching to a string literal if the user
    // enters a quote character
    if (
      [`'`, `"`].includes(e.key) &&
      focusedNodeOrOp &&
      HL.isEditingNode(focusedNodeOrOp) &&
      HL.couldBeReplacedByType(focusedNodeOrOp, tailNode, 'string')
    ) {
      e.preventDefault();
      const currentlyEditingStringLiteral = focusedNodeOrOp.type === 'string';

      if (currentlyEditingStringLiteral) {
        // "complete" the string literal by moving to the next node
        const nextNodeOrOp = HL.getNextNodeOrOpInTextOrder(
          focusedNodeOrOp,
          tailNode
        );

        if (nextNodeOrOp) {
          focusNodeOrOpAction(
            getLogContext(`completing string literal with ${e.key}`),
            nextNodeOrOp,
            undefined,
            undefined
          );
        }
        return;
      }

      // convert the current node (presumed to be a void) into a
      // string literal
      updateNodeAndFocusAction(
        getLogContext(`converting void buffer '${buffer}' to string literal`),
        constString(buffer)
      );
      return;
    }

    // handle automatically entering the brackets when a user types
    // the [ key (when applicable)
    if (e.key === '[' && cursorAtBeginning) {
      const bracketOpSuggestions = suggestions.filter(
        (
          suggestion
        ): suggestion is AutosuggestResult<CGTypes.EditingOutputNode> => {
          // what op (if any) is this suggestion suggesting?
          let op: CGTypes.EditingOp | undefined;

          if (HL.isEditingOp(suggestion.newNodeOrOp)) {
            op = suggestion.newNodeOrOp;
          } else if (suggestion.newNodeOrOp.fromOp) {
            op = suggestion.newNodeOrOp.fromOp;
          }

          return !!op && HL.isBracketsOp(op);
        }
      );

      // find [] (empty brackets) if it's one of the options
      const voidBracketOp = bracketOpSuggestions.find(suggestion => {
        const arg = Object.values(suggestion.newNodeOrOp.fromOp.inputs)[1];

        return arg.nodeType === 'void';
      });

      if (voidBracketOp) {
        // [] is a valid option, so the user probably wanted to move
        // into the brackets -- let's do that right away instead of
        // making them hit Enter:
        updateNodeAndFocusAction(
          getLogContext('moving from void into brackets because [ pressed'),
          voidBracketOp.newNodeOrOp
        );
        e.preventDefault();
        return;
      }
    }

    if (e.key === ']' && cursorAtEnd) {
      const bracketAncestor = HL.findContainingBracketNode(
        focusedNodeOrOp,
        tailNode
      );

      if (bracketAncestor) {
        // we *are* in a bracket op, and we *are* at the end of the current input.
        // but are we in the last node inside the brackets?
        //
        // consider `a[3 + 4]`. at this point, the cursor could be:
        // * after `3`
        // * after `+`
        // * after `4`
        //
        // we only want to close the brackets if we're at the end -- so in the case
        // above we want to ensure we're after `4` before proceeding

        const ordered = HL.textOrderedNodesAndOps(bracketAncestor);

        if (focusedNodeOrOp === ordered[ordered.length - 1]) {
          // we're at the last child node in the brackets. that means we should
          // close the brackets and move "forward" -- like pressing right arrow
          // from the brackets node:
          const nextNodeOrOp = HL.getNextNodeOrOpInTextOrder(
            focusedNodeOrOp,
            tailNode
          );

          e.preventDefault();

          // if the brackets node *is* the last node in the current expression, we
          // should focus the brackets node itself
          focusNodeOrOpAction(
            getLogContext(
              'focusing last brackets in expression because ] pressed'
            ),
            nextNodeOrOp || bracketAncestor
          );
          return;
        }
      }
    }

    if (e.key === 'Backspace' && cursorAtBeginning) {
      deletePrevAction(
        getLogContext('deleting previous because backspace pressed')
      );
    }
  };
};

export function useGetLogContext(
  baseOrigin: string,
  originNodeOrOp: CGTypes.EditingNode | CGTypes.EditingOp
): (extendedOrigin: string) => LogContext {
  const {node, debug} = useEESelector(state => ({
    node: state.props.node,
    debug: state.props.debug,
  }));

  return useCallback(
    (extendedOrigin: string) => ({
      graph: node,
      origin: `${baseOrigin}->${extendedOrigin}`,
      originNodeOrOp,
      debug,
    }),
    [baseOrigin, debug, originNodeOrOp, node]
  );
}
