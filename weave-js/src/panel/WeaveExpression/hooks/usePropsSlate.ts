import {Slate} from 'slate-react';
import React, {useMemo} from 'react';
import {useExpressionSuggestionsContext} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';

type PropsSlate = Omit<Parameters<typeof Slate>[0], 'children' | 'editor'>;

// Returns props to pass to slate-react's <Slate> component
export const usePropsSlate = (): PropsSlate => {
  // const {clearSelectedSuggestion} = useExpressionSuggestionsContext();
  // TODO: we might actually just want clearSelectedSuggestion. that won't reset suggestions, just the dropdown selection
  const {clearSuggestions} = useExpressionSuggestionsContext();
  // Wrap onChange so that we reset suggestion index back to top
  // on any interaction
  const onChange = React.useCallback(
    newValue => {
      // setSuggestionIndex(0);
      // clearSelectedSuggestion();
      clearSuggestions();
      // propsOnChange?.(newValue, stack); // TODO: do we need to pass stack in? look at onchange props
    },
    [clearSuggestions]
  );

  // These are the props passed to slate-react's <Slate> component
  return useMemo(
    () =>
      ({
        value: [], // TODO; GET AN ACTUAL VALUE
        onChange,
      } as PropsSlate),
    [onChange]
  );
};
