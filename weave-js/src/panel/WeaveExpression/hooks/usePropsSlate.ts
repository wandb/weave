import {Slate} from 'slate-react';
import React, {useMemo} from 'react';
import {useExpressionSuggestionsContext} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';
import {usePropsContext} from '@wandb/weave/panel/WeaveExpression/contexts/PropsProvider';
import {useSlateEditorContext} from '@wandb/weave/panel/WeaveExpression/contexts/SlateEditorProvider';

type PropsSlate = Omit<Parameters<typeof Slate>[0], 'children' | 'editor'>;

const DEFAULT_SLATEVALUE = [
  {
    type: 'paragraph',
    children: [{text: ''}],
  },
];

// Returns props to pass to slate-react's <Slate> component
export const usePropsSlate = (): PropsSlate => {
  // const {clearSelectedSuggestion} = useExpressionSuggestionsContext();
  // TODO: we might actually just want clearSelectedSuggestion. that won't reset suggestions, just the dropdown selection
  const {expression} = usePropsContext();
  const {clearSuggestions} = useExpressionSuggestionsContext();
  const {slateValue, setSlateValue} = useSlateEditorContext();
  // Wrap onChange so that we reset suggestion index back to top
  // on any interaction
  const onChange = React.useCallback(
    newValue => {
      // setSuggestionIndex(0);
      // clearSelectedSuggestion();
      clearSuggestions();
      setSlateValue(newValue);
      // propsOnChange?.(newValue, stack); // TODO: do we need to pass stack in? look at onchange props
    },
    [clearSuggestions, setSlateValue]
  );
  console.log({expression, slateValue});

  // These are the props passed to slate-react's <Slate> component
  return useMemo(
    () =>
      ({
        // initialValue: {text: ''},
        initialValue: DEFAULT_SLATEVALUE,
        // initialValue: [
        //   {
        //     type: 'paragraph',
        //     children: [{text: ''}],
        //   },
        // ], // TODO: get an actual value
        onChange,
      } as PropsSlate),
    [onChange]
  );
};
