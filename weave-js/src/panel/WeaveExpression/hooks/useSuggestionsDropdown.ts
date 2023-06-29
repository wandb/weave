// Manages the selection dropdown state
// TODO: how do we get these to keyboard shortcuts? maybe register them from here somehow? but assigning keys here sucks
// i like the idea of registering functions where they live -- so you know they are available as keyboard shortcuts
// then the shortcut context can manage collisions, i guess? but it'd be also nice to have a comprehensive list of shortcuts in the context
// TODO: maybe rename this? doesn't really have anything to do with suggestions, it's just a generic select-from-a-list hook
import {useCallback, useMemo, useState} from 'react';
import {AutosuggestResult} from '@wandb/weave/core';

// TODO: move this
export type AutosuggestResultAny = AutosuggestResult<any>; // TODO: fix any. also why is it 'autosuggest' and not just 'suggest'?

export const useSuggestionsDropdown = ({
  suggestionItems,
  acceptSuggestion,
}: {
  suggestionItems: AutosuggestResultAny[];
  acceptSuggestion: (s?: AutosuggestResultAny) => void;
}) => {
  // This is the currently-highlighted suggestion in the dropdown
  const [selectedSuggestion, setSelectedSuggestion] = useState<
    AutosuggestResultAny | undefined // TODO: fix 'any'
  >(undefined);

  const selectNextOrPreviousSuggestion = useCallback(
    (nextOrPrevious: 'next' | 'previous') => {
      setSelectedSuggestion(currentSuggestion => {
        const currentIndex =
          currentSuggestion == null
            ? -1
            : suggestionItems.indexOf(currentSuggestion); // also returns -1 if not found
        const newIndex =
          nextOrPrevious === 'next'
            ? (currentIndex + 1) % suggestionItems.length
            : 5;
        return suggestionItems[newIndex];
      });
    },
    [suggestionItems]
  );

  const selectNextSuggestion = useCallback(
    () => selectNextOrPreviousSuggestion('next'),
    [selectNextOrPreviousSuggestion]
  );

  const selectPreviousSuggestion = useCallback(
    () => selectNextOrPreviousSuggestion('previous'),
    [selectNextOrPreviousSuggestion]
  );

  const acceptSelectedSuggestion = useCallback(() => {
    acceptSuggestion(selectedSuggestion);
  }, [acceptSuggestion, selectedSuggestion]);

  const clearSelectedSuggestion = useCallback(() => {
    // // from state.ts:clearSuggestions() , do we still need it?
    // this.suggestionTarget = null
    // this.set('suggestions', {
    //     node: voidNode(),
    //     typeStr: null,
    //     items: [],
    //     isBusy: false,
    // });
    setSelectedSuggestion(undefined);
  }, []);

  return useMemo(
    () => ({
      selectedSuggestion,
      acceptSelectedSuggestion,
      clearSelectedSuggestion,
      selectNextSuggestion,
      selectPreviousSuggestion,
    }),
    [
      acceptSelectedSuggestion,
      clearSelectedSuggestion,
      selectNextSuggestion,
      selectPreviousSuggestion,
      selectedSuggestion,
    ]
  );
};
