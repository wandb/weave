import React, {KeyboardEventHandler} from 'react';
import {ReactEditor} from 'slate-react';
import {useWeaveExpressionContext} from '@wandb/weave/panel/WeaveExpression/contexts/WeaveExpressionContext';
import {useExpressionSuggestions} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';

export const useWeaveExpressionHotkeys = () => {
  const {toggleIsDocsPanelVisible} = useWeaveExpressionContext();
  const {
    acceptSelectedSuggestion,
    selectPreviousSuggestion,
    selectNextSuggestion,
    isEmpty: noSuggestions,
  } = useExpressionSuggestions();

  const onKeyDown: KeyboardEventHandler<HTMLDivElement> = React.useCallback(
    ev => {
      ev.preventDefault();
      ev.stopPropagation();
      const isKey = (key: string) => ev.key === key;
      if (
        // shift key not used for anything right now
        ev.shiftKey ||
        // disable enter key if liveUpdate is enabled
        (isKey('Enter') && liveUpdate) ||
        // disable all other keys if there are no suggestions
        (!isKey('Enter') && noSuggestions)
      ) {
        return;
      }
      if (ev.shiftKey) {
        switch (ev.key) {
          case 'd':
            toggleIsDocsPanelVisible();
        }
      }
      switch (ev.key) {
        case 'Enter':
          // Apply outstanding changes to expression
          if (!isBusy && isValid && isDirty) {
            // get your mind out of the gutter.
            applyPendingExpr();
            forceRender({});
          }
          hideSuggestions(500);
          break;
        case 'Tab':
          // Apply selected suggestion
          acceptSelectedSuggestion();
          // takeSuggestion(suggestions.items[suggestionIndex]);
          break;
        case 'Escape':
          // Blur the editor, hiding suggestions
          ReactEditor.blur(editor);
          forceRender({});
          break;
        // case 'j': // for vim users :)
        case 'ArrowDown':
          // Select next suggestion
          selectNextSuggestion();
          break;
        // case 'k':
        case 'ArrowUp':
          // Select previous suggestion
          selectPreviousSuggestion();
          break;
        case 'ArrowRight':
          toggleIsDocsPanelVisible(true);
          break;
        case 'ArrowLeft':
          toggleIsDocsPanelVisible(false);
          break;
      }

      // if (isKey('Enter')) {
      //   // Apply outstanding changes to expression
      //   if (exprIsModified && isValid && !isBusy) {
      //     applyPendingExpr();
      //     forceRender({});
      //   }
      //   hideSuggestions(500);
      //   return;
      // }
      // if (ev.key === 'Tab' && suggestions.items.length > 0) {
      //   // Apply selected suggestion
      //   takeSuggestion(suggestions.items[suggestionIndex]);
      // } else if (ev.key === 'Escape') {
      //   // Blur the editor, hiding suggestions
      //   ReactEditor.blur(editor);
      //   forceRender({});
      // } else if (
      //   ev.key === 'ArrowDown' &&
      //   !ev.shiftKey &&
      //   suggestions.items.length > 0
      // ) {
      //   // Suggestion cursor down
      //   setSuggestionIndex((suggestionIndex + 1) % suggestions.items.length);
      // } else if (
      //   ev.key === 'ArrowUp' &&
      //   !ev.shiftKey &&
      //   suggestions.items.length > 0
      // ) {
      //   // Suggestion cursor up
      //   setSuggestionIndex(
      //     (suggestions.items.length + suggestionIndex - 1) %
      //       suggestions.items.length
      //   );
      // } else if (
      //   ev.key === 'ArrowRight' &&
      //   !ev.shiftKey &&
      //   suggestions.items.length > 0
      // ) {
      //   toggleIsOpDocEnabled(true);
      // }
    },
    [
      acceptSelectedSuggestion,
      noSuggestions,
      selectNextSuggestion,
      selectPreviousSuggestion,
      toggleIsDocsPanelVisible,
    ]
  );
  return {onKeyDown};
};
