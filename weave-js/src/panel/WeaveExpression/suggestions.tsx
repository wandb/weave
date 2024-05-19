import {ConstNode, isOutputNode} from '@wandb/weave/core';
import _ from 'lodash';
import * as React from 'react';
import {createPortal} from 'react-dom';

import {useWeaveContext} from '../../context';
import {
  useSuggestionTakerWithSlateStaticEditor,
  useSuggestionVisualState,
} from './hooks';
import * as S from './styles';
import {SuggestionRow} from './SuggestionRow';
import type {SuggestionProps} from './types';
import {trace} from './util';

export const Suggestions = (props: SuggestionProps) => {
  const weave = useWeaveContext();
  const {paneRef, showType} = useSuggestionVisualState(props);
  const {takeSuggestion} = useSuggestionTakerWithSlateStaticEditor(
    props,
    weave
  );

  // The tooltip can either appear on hover or be pinned open by clicking the info icon.
  const [isOverInfo, setIsOverInfo] = React.useState<boolean>(false);
  const [isOpenInfo, setIsOpenInfo] = React.useState<boolean>(false);

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
  const onClose = isOpenInfo
    ? () => {
        setIsOverInfo(false);
        setIsOpenInfo(false);
      }
    : undefined;

  const items = _.groupBy(props.items, 'category');
  let itemIndex = 0;

  return createPortal(
    <S.SuggestionContainer ref={paneRef}>
      <S.SuggestionPane data-test="suggestion-pane" isBusy={props.isBusy}>
        {showType ? <div className="type-display">{props.typeStr}</div> : null}
        <ul className="items-list">
          {Object.keys(items).map(suggestionCategory => (
            <React.Fragment key={suggestionCategory}>
              <S.SuggestionCategory>{suggestionCategory}</S.SuggestionCategory>
              {items[suggestionCategory].map((s: any) => {
                itemIndex++;
                return (
                  <SuggestionRow
                    key={itemIndex}
                    idx={itemIndex}
                    suggestion={s}
                    takeSuggestion={takeSuggestion}
                    suggestionIndex={props.suggestionIndex}
                    setSuggestionIndex={props.setSuggestionIndex}
                    hasInfo={activeOpName != null}
                    setIsOverInfo={setIsOverInfo}
                    isOpenInfo={isOpenInfo}
                    setIsOpenInfo={setIsOpenInfo}
                  />
                );
              })}
            </React.Fragment>
          ))}
        </ul>
      </S.SuggestionPane>
      {(isOpenInfo || isOverInfo) && activeOpName && (
        <S.StyledOpDoc
          opName={activeOpName}
          attributeName={activeOpAttrName}
          onClose={onClose}
        />
      )}
    </S.SuggestionContainer>,
    document.body
  );
};
