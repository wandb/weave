import {ConstNode, isOutputNode} from '@wandb/weave/core';
import * as React from 'react';
import {createPortal} from 'react-dom';

import {useSuggestionVisualState} from './hooks';
import * as S from './styles';
import {trace} from './util';
import './styles/Suggestions.less';
import classNames from 'classnames';
import {useExpressionSuggestionsContext} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';

export const Suggestions = () => {
  // const {isBusy, items, suggestionIndex, typeStr} = props;
  // TODO: do we need to fix useSuggestionVisualState?
  const {paneRef, showType} = useSuggestionVisualState();
  // const {acceptS} = useExpressionSuggestionsWithSlateStaticEditor(); // does this need static editor?
  const {
    acceptSelectedSuggestion,
    // TODO: rename isBusy
    suggestions: {isBusy, items, suggestionIndex, typeStr},
  } = useExpressionSuggestionsContext();
  // const {isDocsPanelVisible} = useWeaveExpressionContext();
  const isDocsPanelVisible = true; // TODO: fix this

  // TODO: review all of this
  const activeOpName = React.useMemo<string | null>(() => {
    if (
      items == null ||
      suggestionIndex == null ||
      items[suggestionIndex] == null
    ) {
      return null;
    }

    const newNodeOrOp = items[suggestionIndex].newNodeOrOp;
    if (isOutputNode(newNodeOrOp)) {
      return newNodeOrOp.fromOp.name;
    }

    return null;
  }, [items, suggestionIndex]);

  const activeOpAttrName = React.useMemo<string | undefined>(() => {
    if (
      items == null ||
      suggestionIndex == null ||
      items[suggestionIndex] == null
    ) {
      return undefined;
    }

    const newNodeOrOp = items[suggestionIndex].newNodeOrOp;
    if (
      isOutputNode(newNodeOrOp) &&
      newNodeOrOp.fromOp.name.endsWith('__getattr__')
    ) {
      return (newNodeOrOp.fromOp.inputs.name as ConstNode).val;
    }

    return undefined;
  }, [items, suggestionIndex]);

  // TODO: figure out general/boilerplate trace behavior
  trace(`Render Suggestions`, activeOpName, paneRef.current, showType);

  return createPortal(
    <div className="suggestions" ref={paneRef}>
      <div
        className={classNames('suggestion-pane', {isBusy})}
        data-test="suggestion-pane">
        <ul className="items-list">
          {items.map((s: any, idx: number) => (
            <li
              className={
                (idx === suggestionIndex ? 'default-suggestion ' : '') +
                SUGGESTION_OPTION_CLASS
              }
              key={idx}
              onMouseDown={ev => {
                // Prevent this element from taking focus
                // otherwise it disappears before the onClick
                // can register!
                ev.preventDefault();
              }}
              onClick={acceptSelectedSuggestion}>
              {s.suggestionString.trim()}
            </li>
          ))}
        </ul>
        {showType ? <div className="type-display">{typeStr}</div> : null}
      </div>
      {activeOpName && isDocsPanelVisible && (
        <S.StyledOpDoc opName={activeOpName} attributeName={activeOpAttrName} />
      )}
    </div>,
    document.body
  );
};

// TODO: this is not the right way to do this
export const SUGGESTION_OPTION_CLASS = 'suggestion-option';
