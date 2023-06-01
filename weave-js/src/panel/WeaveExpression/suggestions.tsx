import {isOutputNode} from '@wandb/weave/core';
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

export const Suggestions = (props: SuggestionProps) => {
  const weave = useWeaveContext();
  const {paneRef, showType} = useSuggestionVisualState(props);
  const {takeSuggestion} = useSuggestionTakerWithSlateStaticEditor(
    props,
    weave
  );

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

  trace(`Render Suggestions`, props, activeOpName, paneRef.current, showType);

  return createPortal(
    <S.SuggestionContainer ref={paneRef}>
      <S.SuggestionPane data-test="suggestion-pane" isBusy={props.isBusy}>
        {showType ? <div className="type-display">{props.typeStr}</div> : null}
        <ul className="items-list">
          {props.items.map((s: any, idx: number) => (
            <li
              className={
                (idx === props.suggestionIndex ? 'default-suggestion ' : '') +
                S.SUGGESTION_OPTION_CLASS
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
      </S.SuggestionPane>
      {activeOpName && <S.StyledOpDoc opName={activeOpName} />}
    </S.SuggestionContainer>,
    document.body
  );
};
