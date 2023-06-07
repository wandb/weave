import React from 'react';
import {ReactEditor} from 'slate-react';
import {useWeaveExpressionContext} from '@wandb/weave/panel/WeaveExpression/contexts/WeaveExpressionContext';
import {useSuggestionTaker} from '@wandb/weave/panel/WeaveExpression/hooks';

const useWeaveExpressionHotkeys = () => {
  const {toggleIsDocsPanelVisible} = useWeaveExpressionContext();
  const {takeSuggestion, suggestionIndex, setSuggestionIndex} =
    useSuggestionTaker();

  const keyDownHandler = React.useCallback(
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
        (!isKey('Enter') && suggestions.items.length === 0)
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
          if (isDirty && isValid && !isBusy) {
            applyPendingExpr();
            forceRender({});
          }
          hideSuggestions(500);
          break;
        case 'Tab':
          // Apply selected suggestion
          takeSuggestion(suggestions.items[suggestionIndex]);
          break;
        case 'Escape':
          // Blur the editor, hiding suggestions
          ReactEditor.blur(editor);
          forceRender({});
          break;
        // case 'j': // for vim users :)
        case 'ArrowDown':
          // Select next suggestion
          setSuggestionIndex((suggestionIndex + 1) % suggestions.items.length);
          break;
        // case 'k':
        case 'ArrowUp':
          // Select previous suggestion
          setSuggestionIndex(
            (suggestions.items.length + suggestionIndex - 1) %
              suggestions.items.length
          );
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
      props.liveUpdate,
      suggestions.items,
      exprIsModified,
      isValid,
      isBusy,
      hideSuggestions,
      takeSuggestion,
      suggestionIndex,
      editor,
      setSuggestionIndex,
      toggleIsDocsPanelVisible,
      applyPendingExpr,
    ]
  );
};
