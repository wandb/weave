import {Slate, withReact} from 'slate-react';
import React, {useMemo} from 'react';
import {withHistory} from 'slate-history';
import {createEditor} from 'slate';

type PropsSlate = Omit<Parameters<typeof Slate>[0], 'children'>;

const DEFAULT_SLATEVALUE = [
  {
    type: 'paragraph',
    children: [{text: ''}],
  },
];

// Returns props to pass to slate-react's <Slate> component
export const usePropsSlate = (): PropsSlate => {
  const slateEditor = withReact(withHistory(createEditor())); // as any))
  // const {clearSelectedSuggestion} = useExpressionSuggestionsContext();
  // TODO: we might actually just want clearSelectedSuggestion. that won't reset suggestions, just the dropdown selection
  // const {expression} = usePropsContext();
  // TODO: re-enable clearSuggestions and setSlateValue? or maybe we don't need slate value, just get it from editor
  // const {clearSuggestions} = useExpressionSuggestionsContext();
  // const {setSlateValue} = useExpressionEditorContext();
  // Wrap onChange so that we reset suggestion index back to top
  // on any interaction
  const onChange = React.useCallback(newValue => {
    // setSuggestionIndex(0);
    // clearSelectedSuggestion();
    // clearSuggestions();
    // setSlateValue(newValue);
    // propsOnChange?.(newValue, stack); // TODO: do we need to pass stack in? look at onchange props
  }, []);
  // console.log({expression, slateValue});

  // These are the props passed to slate-react's <Slate> component
  return useMemo(
    () =>
      ({
        editor: slateEditor,
        initialValue: DEFAULT_SLATEVALUE,
        // initialValue: [
        //   {
        //     type: 'paragraph',
        //     children: [{text: ''}],
        //   },
        // ], // TODO: get an actual value
        onChange,
      } as PropsSlate),
    [onChange, slateEditor]
  );
};
