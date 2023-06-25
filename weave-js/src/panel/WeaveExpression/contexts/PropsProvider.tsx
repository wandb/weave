import {SlateEditorProviderInput} from '@wandb/weave/panel/WeaveExpression/contexts/SlateEditorProvider';
import {ExpressionSuggestionsProviderInput} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';
import {PropsEditableInput} from '@wandb/weave/panel/WeaveExpression/hooks/usePropsEditable';
import React, {FC, PropsWithChildren, useMemo} from 'react';
import {
  GenericProvider,
  useGenericContext,
} from '@wandb/weave/panel/WeaveExpression/contexts/GenericProvider';
import {WeaveExpressionProps} from '@wandb/weave/panel/WeaveExpression/WeaveExpression';
import {PropsRunButtonInput} from '@wandb/weave/panel/WeaveExpression/RunExpressionButton';

interface PropsProviderInput {
  value: WeaveExpressionProps;
}

interface PropsProviderOutput {
  slateEditorProviderInput: SlateEditorProviderInput;
  expressionSuggestionsProviderInput: ExpressionSuggestionsProviderInput;
  propsEditableInput: PropsEditableInput;
  propsRunButtonInput: PropsRunButtonInput;
  expression: PropsProviderInput['value']['expression'];
}

// This provider takes in all of the top-level props (via the `value` prop),
// then groups and memoizes them based on their usage, and exports those prop groups.
// These prop groups are the inputs to providers and hooks further down the tree.
export const PropsProvider: FC<PropsWithChildren<PropsProviderInput>> = ({
  value: {
    onBlur,
    onFocus,
    onMount,
    expression,
    setExpression,
    isLiveUpdateEnabled,
    isTruncated,
  },
  children,
}) => {
  const slateEditorProviderInput: SlateEditorProviderInput = useMemo(
    () => ({
      onMount,
    }),
    [onMount]
  );
  const expressionSuggestionsProviderInput: ExpressionSuggestionsProviderInput =
    useMemo(
      () => ({
        expression,
        setExpression,
        isLiveUpdateEnabled,
      }),
      [expression, isLiveUpdateEnabled, setExpression]
    );
  const propsEditableInput: PropsEditableInput = useMemo(
    () => ({
      onBlur,
      onFocus,
    }),
    [onBlur, onFocus]
  );
  const propsRunButtonInput: PropsRunButtonInput = useMemo(
    () => ({isTruncated, isLiveUpdateEnabled}),
    [isLiveUpdateEnabled, isTruncated]
  );

  const contextValue: PropsProviderOutput = useMemo(
    () => ({
      slateEditorProviderInput,
      expressionSuggestionsProviderInput,
      propsEditableInput,
      propsRunButtonInput,
      expression,
    }),
    [
      slateEditorProviderInput,
      expressionSuggestionsProviderInput,
      propsEditableInput,
      propsRunButtonInput,
      expression,
    ]
  );
  return (
    <GenericProvider<PropsProviderOutput>
      value={contextValue}
      displayName={'PropsContext'}>
      {children}
    </GenericProvider>
  );
};
export const usePropsContext = () =>
  useGenericContext<PropsProviderOutput>({displayName: 'PropsContext'});
