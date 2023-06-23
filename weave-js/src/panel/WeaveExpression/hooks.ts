import React from 'react';
import {Range} from 'slate';
import {useFocused, useSlateStatic} from 'slate-react';

import {trace} from './util';
import {useExpressionSuggestionsContext} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';

// Managed suggestions component state
// TODO: review all of this
export const useSuggestionVisualState = () => {
  const {
    suggestions: {node, typeStr, items, forceHidden},
  } = useExpressionSuggestionsContext();
  const paneRef = React.useRef<HTMLDivElement | null>(null);
  const editor = useSlateStatic();
  const focused = useFocused();

  // Manage suggestions pane visibility and positioning
  React.useEffect(() => {
    const element = paneRef.current;

    if (!element) {
      trace(`SuggestionVisualState: no element`);
      return;
    }

    if (
      items.length === 0 ||
      !focused ||
      forceHidden ||
      (editor.selection != null && Range.isExpanded(editor.selection))
    ) {
      trace(
        `SuggestionVisualState: hiding`,
        items.length,
        focused,
        forceHidden,
        editor.selection != null && Range.isExpanded(editor.selection)
      );
      element.removeAttribute('style');
      return;
    }

    const domSelection = window.getSelection()!;

    // Hack around a bug where empty spans yield bounding rect of [0,0]->[0,0]
    if (domSelection.rangeCount < 1) {
      trace(`SuggestionVisualState: rangeCount < 1, removing style`);
      element.removeAttribute('style');
      return;
    }

    const domRange = domSelection.getRangeAt(0).cloneRange();
    domRange.setStart(domRange.startContainer, 0);
    let rect = domRange.getBoundingClientRect();

    if (rect.top === 0 && rect.left === 0) {
      rect = (domRange.startContainer as any).getBoundingClientRect();
    }

    if (rect.top === 0 && rect.left === 0) {
      trace(
        `SuggestionVisualState: rect is [0,0]->[0,0], removing style`,
        domRange,
        rect
      );
      element.removeAttribute('style');
      return;
    }

    trace(`SuggestionVisualState: showing`);
    element.style.opacity = '1';
    element.style.top = `${rect.top + window.pageYOffset + 25}px`;

    // Prevent suggestions pane from extending off the page
    const maxLeftPosition = document.body.scrollWidth - 510;
    const naturalLeftPosition = rect.right + window.pageXOffset;
    element.style.left = `${Math.min(maxLeftPosition, naturalLeftPosition)}px`;

    rect = element.getBoundingClientRect();
    if (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <=
        (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    ) {
      element
        .querySelector('ul.items-list li.default-suggestion')!
        .scrollIntoView({block: 'nearest', inline: 'nearest'});
    }
  });

  const showType = React.useMemo(() => {
    if (
      node.nodeType === 'void' ||
      typeStr == null ||
      ['any', 'unknown', 'invalid'].includes(typeStr)
    ) {
      return false;
    }

    return true;
  }, [node, typeStr]);

  return {
    // Ref to pass to SuggestionPane component, req'd to manage its position
    paneRef,

    // Should we show the type?
    showType,
  };
};
