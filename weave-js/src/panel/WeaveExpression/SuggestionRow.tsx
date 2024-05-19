import * as globals from '@wandb/weave/common/css/globals.styles';
import type {AutosuggestResult} from '@wandb/weave/core';
import _ from 'lodash';
import React from 'react';
import styled from 'styled-components';

import {IconInfo} from '../../components/Panel2/Icons';
import * as S from './styles';

export const Row = styled.div`
  position: relative;
  height: 24px;
`;
Row.displayName = 'S.Row';

export const Suggestion = styled.div`
  position: absolute;
  left: 0;
`;
Suggestion.displayName = 'S.Suggestion';

export const Info = styled.div<{isOpenInfo: boolean}>`
  background-color: ${globals.MOON_100};
  position: absolute;
  top: 0;
  bottom: 0;
  right: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 0 10px;

  color: ${props => (props.isOpenInfo ? globals.MOON_800 : globals.MOON_450)};
  &:hover {
    color: ${globals.MOON_800};
  }
`;
Info.displayName = 'S.Info';

type SuggestionRowProps = {
  suggestion: AutosuggestResult<any>;
  idx: number;
  suggestionIndex?: number;
  setSuggestionIndex?: React.Dispatch<React.SetStateAction<number>>;
  takeSuggestion: (s: AutosuggestResult<any>) => void;

  hasInfo: boolean;
  setIsOverInfo: React.Dispatch<React.SetStateAction<boolean>>;
  isOpenInfo: boolean;
  setIsOpenInfo: React.Dispatch<React.SetStateAction<boolean>>;
};

export const SuggestionRow = ({
  suggestion,
  idx,
  suggestionIndex,
  setSuggestionIndex,
  takeSuggestion,
  hasInfo,
  setIsOverInfo,
  isOpenInfo,
  setIsOpenInfo,
}: SuggestionRowProps) => {
  const isDefault = idx === suggestionIndex;
  const openPopup = () => setIsOverInfo(true);
  const onMouseEnter = _.debounce(() => {
    setTimeout(openPopup, 400);
  }, 400);
  const onMouseLeave = () => {
    onMouseEnter.cancel();
    setIsOverInfo(false);
  };
  const onClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (isOpenInfo) {
      setIsOverInfo(false);
    }
    setIsOpenInfo(!isOpenInfo);
  };
  return (
    <li
      className={
        (isDefault ? 'default-suggestion ' : '') + S.SUGGESTION_OPTION_CLASS
      }
      // Note: we don't clear the suggestion index on mouse leave - we want
      // it to remain in case the user is just mousing over to click on something
      // in the op doc.
      onMouseEnter={
        setSuggestionIndex ? () => setSuggestionIndex(idx) : undefined
      }
      onMouseDown={ev => {
        // Prevent this element from taking focus
        // otherwise it disappears before the onClick
        // can register!
        ev.preventDefault();
      }}
      onClick={() => takeSuggestion(suggestion)}>
      <Row>
        <Suggestion>{suggestion.suggestionString.trim()}</Suggestion>
        {isDefault && hasInfo && (
          <Info
            isOpenInfo={isOpenInfo}
            onMouseEnter={onMouseEnter}
            onMouseLeave={onMouseLeave}
            onClick={onClick}>
            <IconInfo width={18} height={18} />
          </Info>
        )}
      </Row>
    </li>
  );
};
