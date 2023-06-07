import {ConstNode, isOutputNode} from '@wandb/weave/core';
import * as React from 'react';
import {createPortal} from 'react-dom';

import {useWeaveContext} from '../../context';
import {
  useSuggestionTakerWithSlateStaticEditor,
  useSuggestionVisualState,
} from './hooks';
import * as S from './styles';
import type {SuggestionProps} from './types';
import {trace} from './util';
import './styles/Suggestions.less';
import {useWeaveExpressionContext} from '@wandb/weave/panel/WeaveExpression/WeaveExpression';
import classNames from 'classnames';

export const Suggestions = (props: SuggestionProps) => {
  const {isBusy} = props;
  const weave = useWeaveContext();
  const {paneRef, showType} = useSuggestionVisualState(props);
  const {takeSuggestion} = useSuggestionTakerWithSlateStaticEditor(
    props,
    weave
  );
  const {isOpDocEnabled} = useWeaveExpressionContext();

  const activeOpName = React.useMemo<string | null>(() => {
    if (
      props.items == null ||
      props.suggestionIndex == null ||
      props.items[props.suggestionIndex] == null
    ) {
      return null;
    }

    const newNodeOrOp = props.items[props.suggestionIndex].newNodeOrOp;
    if (isOutputNode(newNodeOrOp)) {
      return newNodeOrOp.fromOp.name;
    }

    return null;
  }, [props.items, props.suggestionIndex]);

  const activeOpAttrName = React.useMemo<string | undefined>(() => {
    if (
      props.items == null ||
      props.suggestionIndex == null ||
      props.items[props.suggestionIndex] == null
    ) {
      return undefined;
    }

    const newNodeOrOp = props.items[props.suggestionIndex].newNodeOrOp;
    if (
      isOutputNode(newNodeOrOp) &&
      newNodeOrOp.fromOp.name.endsWith('__getattr__')
    ) {
      return (newNodeOrOp.fromOp.inputs.name as ConstNode).val;
    }

    return undefined;
  }, [props.items, props.suggestionIndex]);

  trace(`Render Suggestions`, props, activeOpName, paneRef.current, showType);

  return createPortal(
    <div className="suggestions" ref={paneRef}>
      <div
        className={classNames('suggestion-pane', {isBusy})}
        data-test="suggestion-pane">
        <ul className="items-list">
          {props.items.map((s: any, idx: number) => (
            <li
              className={
                (idx === props.suggestionIndex ? 'default-suggestion ' : '') +
                SUGGESTION_OPTION_CLASS
              }
              key={idx}
              onMouseDown={ev => {
                // Prevent this element from taking focus
                // otherwise it disappears before the onClick
                // can register!
                ev.preventDefault();
              }}
              onClick={() => takeSuggestion(s)}>
              {s.suggestionString.trim()}
            </li>
          ))}
        </ul>
        {showType ? <div className="type-display">{props.typeStr}</div> : null}
      </div>
      {activeOpName && isOpDocEnabled && (
        <S.StyledOpDoc opName={activeOpName} attributeName={activeOpAttrName} />
      )}
    </div>,
    document.body
  );
};

// TODO: this is not the right way to do this
export const SUGGESTION_OPTION_CLASS = 'suggestion-option';
