import {
  EditingNode,
  NodeOrVoidNode,
  Stack,
  WeaveInterface,
} from '@wandb/weave/core';
import {useDeepMemo} from '@wandb/weave/hookUtils';
import React, {useCallback, useRef} from 'react';

import {makeEventRecorder} from '../panellib/libanalytics';
import * as Table from './tableState';

const recordEvent = makeEventRecorder('Table');

export function useUpdatePanelConfig(
  updateTableState: (newTableState: Table.TableState) => void,
  tableState: Table.TableState,
  colId: string
) {
  return useCallback(
    (newPanelConfig: any) => {
      recordEvent('UPDATE_PANEL_CONFIG');
      return updateTableState(
        Table.updateColumnPanelConfig(tableState, colId, newPanelConfig)
      );
    },
    [colId, tableState, updateTableState]
  );
}

type PromiseFn = (...args: any[]) => Promise<any>;
type Loadable<T> =
  | {initialLoading: boolean; loading: false; result: T}
  | {initialLoading: boolean; loading: true; result: undefined};

// backport of Awaited which was introduced first-class in TS4.5
// source: https://stackoverflow.com/a/49889856
type Awaited<T> = T extends PromiseLike<infer U>
  ? {0: Awaited<U>; 1: U}[U extends PromiseLike<any> ? 0 : 1]
  : T;

function argsEqual(args: any[], otherArgs?: any[]): boolean {
  if (otherArgs == null) {
    return false;
  }
  if (args.length !== otherArgs.length) {
    return false;
  }
  return args.every((arg, i) => otherArgs[i] === arg);
}

export function makePromiseUsable<
  PF extends PromiseFn,
  PT extends any[] = Parameters<PF>,
  RT = Awaited<ReturnType<PF>>
>(promiseFn: PF): (...args: PT) => Loadable<RT> {
  return (...inputArgs: PT) => {
    const args = useDeepMemo(inputArgs);
    const initialLoading = useRef(true);
    const calledWithArgsRef = React.useRef<PT>();
    const [promiseResult, setPromiseResult] = React.useState<
      {resultFromArgs: PT; result: RT} | undefined
    >();
    // If the args passed to the function do not match the last promise execution...
    if (!argsEqual(args, calledWithArgsRef.current)) {
      // Then execute the promise again, and retain a reference to the new args.
      calledWithArgsRef.current = args;
      promiseFn(...args).then(res => {
        // When the results come back, verify that the args match what was called.
        // The reason this could be different is that `args` will be trapped in the closure
        // as the values that the promise was called with. However, if another call was made
        // before the promise resolves, then `calledWithArgsRef.current` will be set to the
        // latest call. If they are not equal, then we skip the update (since it is outdated).
        // However, if they are equal, then we update the promise result.
        if (argsEqual(args, calledWithArgsRef.current)) {
          initialLoading.current = false;
          setPromiseResult({resultFromArgs: args, result: res});
        }
      });
    }

    // Finally, we want to return a memoed object that updates
    // when new args come in or new promise results come in.
    return React.useMemo(() => {
      // If the promiseResult state is null (no promise has resolved)
      // or the promiseResult is stale (indicated by the resultFromArgs
      // no longer equalling the current rendered args...)
      if (
        promiseResult == null ||
        !argsEqual(args, promiseResult.resultFromArgs)
      ) {
        // Then return loading
        return {
          initialLoading: initialLoading.current,
          loading: true,
          result: undefined,
        };
      } else {
        // Else return the promise results
        return {
          initialLoading: initialLoading.current,
          loading: false,
          result: promiseResult.result,
        };
      }
    }, [args, promiseResult]);
  };
}

type VectorizedFn<F> = F extends (
  a: infer A1,
  ...args: infer U
) => Promise<infer R>
  ? (list: A1[], ...args: U) => Promise<R[]>
  : unknown;

export function vectorizePromiseFn<PF extends PromiseFn>(
  promiseFn: PF
): VectorizedFn<PF> {
  const resFn = (...args: Parameters<VectorizedFn<PF>>) => {
    return Promise.all(args[0].map(a => promiseFn(a, ...args.slice(1))));
  };
  return resFn as VectorizedFn<PF>;
}

export type RefineEditingNodeType = (
  expression: EditingNode,
  stack: Stack
) => Promise<EditingNode>;

// Promise Versions:
// Single refiner
export const refineExpression = async (
  expression: NodeOrVoidNode,
  stack: Stack,
  weave: WeaveInterface
) => {
  // Use real internal function
  return await weave.refineNode(expression, stack);
};

// Refines a list of expressions with a single frame
export const refineExpressions = vectorizePromiseFn(refineExpression);
