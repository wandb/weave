/* This is nestable context available to Panel2 panels */
import {
  Definition,
  Frame,
  getFreeVars,
  Node,
  NodeOrVoidNode,
  pushFrame,
  resolveVar,
} from '@wandb/weave/core';
import {getChainRootVar} from '@wandb/weave/core/mutate';
import {consoleGroup, consoleLog} from '@wandb/weave/util';
import React, {ReactNode, useCallback, useContext, useMemo} from 'react';

import {useDeepMemo} from '../../hookUtils';

interface ExpressionEventHover {
  id: 'hover';
}

interface ExpressionEventUnhover {
  id: 'unhover';
}

interface ExpressionEventMutate {
  id: 'mutate';
  newRootNode: NodeOrVoidNode;
}

export type ExpressionEvent =
  | ExpressionEventHover
  | ExpressionEventUnhover
  | ExpressionEventMutate;

type DefinitionWithEventHandler = Definition & {
  handleVarEvent?: (
    varName: string,
    target: NodeOrVoidNode,
    event: ExpressionEvent
  ) => void;
};

export type StackWithHandlers = DefinitionWithEventHandler[];

const propagateExpressionEvent = (
  target: NodeOrVoidNode,
  event: ExpressionEvent,
  stack: StackWithHandlers,
  bubbleBy: 'chain' | 'all',
  notifyWhom: 'path' | 'root'
): void => {
  consoleGroup();
  consoleLog('propagateExpressionEvent', target, stack, event, bubbleBy);
  const getExpressionVars = (node: NodeOrVoidNode) => {
    if (bubbleBy === 'chain') {
      const rootVar = getChainRootVar(node);
      if (rootVar) {
        return [rootVar];
      }
      return [];
    }
    return getFreeVars(node);
  };

  const walkVars = getExpressionVars(target);

  for (const walkVar of walkVars) {
    consoleLog('walking var', walkVar);
    const resolved = resolveVar(stack, walkVar.varName);
    if (resolved != null) {
      consoleLog('resolved var', resolved);
      const {closure, entry} = resolved;
      const {stack: newStack, value: newTarget} = closure;
      const {handleVarEvent} = entry;
      if (notifyWhom === 'root') {
        const isRoot = getExpressionVars(newTarget).length === 0;
        if (isRoot) {
          if (handleVarEvent != null) {
            handleVarEvent(walkVar.varName, newTarget, event);
          }
        } else {
          consoleLog('not root');
          propagateExpressionEvent(
            newTarget,
            event,
            newStack,
            bubbleBy,
            notifyWhom
          );
        }
      } else {
        if (handleVarEvent != null) {
          handleVarEvent(walkVar.varName, newTarget, event);
        }
        propagateExpressionEvent(target, event, stack, bubbleBy, notifyWhom);
      }
    }
  }
  console.groupEnd();
};

export interface PanelContextState {
  frame: Frame;
  lastFrame: Frame;
  stack: StackWithHandlers;
  path: string[];

  // TODO: currently only populated in config component hierarchy
  // but may want it in component hierarchy to highlight selected
  // panel
  selectedPath?: string[];

  // Use to inform useNodeValue that we're inside PanelMaybe.
  panelMaybeNode: Node | null;

  triggerExpressionEvent: (
    target: NodeOrVoidNode,
    event: ExpressionEvent,
    // How to propagate along the DAG. 'chain' means to only to the left
    // most argument of each encountered op. 'all' means to propagate along
    // the entire DAG.
    bubbleBy: 'chain' | 'all',
    // Which handlers to call along the way. If root only the root handler
    // will be called (when there are no var nodes remaining). Otherwise
    // all var node handler's along the way will be called.
    notifyWhom: 'path' | 'root'
  ) => void;

  dashboardConfigOptions?: ReactNode;
}

export const PanelContext = React.createContext<PanelContextState | null>(null);
PanelContext.displayName = 'PanelContext';

const DEFAULT_CONTEXT: PanelContextState = {
  frame: {},
  lastFrame: {},
  stack: [],
  path: [],
  panelMaybeNode: null,
  triggerExpressionEvent: () => {},
};

export function usePanelContext() {
  return useContext(PanelContext) ?? DEFAULT_CONTEXT;
}

// Creates a new stack frame and adds variables to it.
export const PanelContextProvider: React.FC<{
  newVars?: Frame;
  newPath?: string;
  selectedPath?: string[];
  panelMaybeNode?: Node | null;
  // Handle events that occur on consuming expressions of variables
  // added in this frame.
  handleVarEvent?: (
    varName: string,
    target: NodeOrVoidNode,
    event: ExpressionEvent
  ) => void;
  dashboardConfigOptions?: ReactNode;
}> = React.memo(
  ({
    newVars,
    newPath,
    selectedPath,
    children,
    panelMaybeNode,
    handleVarEvent,
    dashboardConfigOptions,
  }) => {
    // A lot of callers pass new vars in without useMemo, so we deep memo
    // here. Could probably get away with memoizing each var be reference
    // instead. But this is safer (maybe more expensive but we'll see it in
    // profiles if problematic).
    newVars = newVars ?? {};
    newVars = useDeepMemo(newVars);
    const {
      frame,
      stack,
      path,
      selectedPath: prevSelectedPath,
    } = usePanelContext();

    const childPath = useMemo(
      () => (newPath ? path.concat(newPath) : path),
      [newPath, path]
    );
    const childFrame = useMemo(
      () => ({...frame, ...newVars}),
      [frame, newVars]
    );
    const childStack = useMemo(
      () => pushFrame(stack, newVars ?? {}, {handleVarEvent}),
      [handleVarEvent, newVars, stack]
    );

    const triggerExpressionEvent: PanelContextState['triggerExpressionEvent'] =
      useCallback(
        (target, event, bubbleBy, notifyWhom) => {
          return propagateExpressionEvent(
            target,
            event,
            childStack,
            bubbleBy,
            notifyWhom
          );
        },
        [childStack]
      );

    const ctxValue: PanelContextState = useMemo(() => {
      return {
        frame: childFrame,
        lastFrame: newVars ?? {},
        stack: childStack,
        path: childPath,
        selectedPath: selectedPath ?? prevSelectedPath,
        panelMaybeNode: panelMaybeNode ?? null,
        triggerExpressionEvent,
        dashboardConfigOptions,
      };
    }, [
      childFrame,
      newVars,
      childStack,
      childPath,
      selectedPath,
      prevSelectedPath,
      panelMaybeNode,
      triggerExpressionEvent,
      dashboardConfigOptions,
    ]);

    return (
      <PanelContext.Provider value={ctxValue}>{children}</PanelContext.Provider>
    );
  }
);
PanelContextProvider.displayName = 'PanelContextProvider';

export const useExpressionHoverHandlers = (node: NodeOrVoidNode) => {
  const {triggerExpressionEvent} = usePanelContext();
  return useMemo(
    () => ({
      onExpressionHover: () => {
        triggerExpressionEvent(node, {id: 'hover'}, 'all', 'path');
      },
      onExpressionUnhover: () => {
        triggerExpressionEvent(node, {id: 'unhover'}, 'all', 'path');
      },
    }),
    [node, triggerExpressionEvent]
  );
};
