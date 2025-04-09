import * as globals from '@wandb/weave/common/css/globals.styles';
import {Button} from 'semantic-ui-react';
import {Editable} from 'slate-react';
import styled, {css} from 'styled-components';

import OpDoc from './OpDoc';

export const IDENTIFER_COLOR = globals.MAGENTA;
export const PROPERTY_IDENTIFIER_COLOR = globals.SIENNA_DARK;
export const OPERATOR_COLOR = globals.SIENNA_DARK;
export const STRING_COLOR = globals.TEAL;
export const BOOLEAN_COLOR = globals.TEAL;
export const NUMBER_COLOR = globals.TEAL;

export const EditableContainer = styled.div<{
  noBox?: boolean;
  isInvalid?: boolean;
}>`
  position: relative;
  display: flex;
  flex: 1 1 auto;

  max-height: 80px;
  overflow: auto;

  ${props =>
    !props.noBox &&
    css`
      border: 1px solid;
      flex-grow: 1;
      border-color: ${(innerProps: {isInvalid?: boolean}) =>
        innerProps.isInvalid ? globals.error : '#bbb'};
      border-radius: 4px;
      padding: 6px 8px;
      min-width: 200px;
      border: 1px solid ${globals.MOON_400};
      border-radius: 4px;
      box-sizing: border-box;

      &:hover {
        border-color: ${globals.TEAL_350};
      }

      &:focus-within {
        border-color: ${globals.TEAL_350};
        outline: 2px solid ${globals.TEAL_350};
        outline-offset: -2px;
      }
    `}
`;
EditableContainer.displayName = 'S.EditableContainer';

export const WeaveEditable = styled(Editable)<{$truncate?: boolean}>`
  width: 100%;
  min-height: 20px;
  line-height: 20px;

  font-family: Inconsolata;
  cursor: text;

  &:focus {
    outline: 0;
  }

  // Req'd to make editor selectable in Safari
  user-select: text;

  &.invalid {
    border-bottom: 1px dotted ${globals.RED};
  }

  & span.identifier {
    color: ${IDENTIFER_COLOR};
  }

  span.property_identifier {
    color: ${PROPERTY_IDENTIFIER_COLOR};
  }

  & span.operator {
    color: ${OPERATOR_COLOR};
  }

  & span.string {
    color: ${STRING_COLOR};
  }

  & span.number,
  & span.null {
    color: ${NUMBER_COLOR};
  }

  & span.boolean {
    color: ${BOOLEAN_COLOR};
  }

  & span.ACTIVE_NODE {
    text-decoration: underline dotted rgba(0, 0, 0, 0.2);
  }

  /* HACK: attempt to hide large object literals
  & span.large_object {
    display: none;
  }
  */

  ${p =>
    p.$truncate &&
    css`
      & > div {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    `}
`;
WeaveEditable.displayName = 'S.WeaveEditable';

export const ApplyButton = styled(Button)`
  display: none;
  font-size: 13px !important;
  line-height: 20px !important;
  padding: 0px !important;
  height: 20px;
  background-color: transparent !important;
  box-shadow: none !important;
  border: none !important;
  width: 28px !important;

  &:disabled {
    color: ${globals.MOON_400} !important;
    background-color: transparent !important;
    opacity: 0.5 !important;
  }

  &:not(:disabled) {
    color: ${globals.TEAL_350} !important;
  }

  &:hover:not(:disabled) {
    background-color: transparent !important;
    color: ${globals.TEAL_400} !important;
  }
`;
ApplyButton.displayName = 'S.ApplyButton';

export const SuggestionContainer = styled.div`
  position: absolute;
  top: -10000px;
  left: -10000px;
  z-index: 2147483647;

  transition: opacity 0.3s;
  opacity: 0;
`;
SuggestionContainer.displayName = 'S.SuggestionContainer';

export const SUGGESTION_OPTION_CLASS = 'suggestion-option';
export const SuggestionPane = styled.div<{isBusy: boolean}>`
  display: inline-block;

  background-color: ${globals.WHITE};
  border: 1px solid ${globals.MOON_250};
  border-radius: 4px;
  box-shadow: 0px 12px 24px 0px rgba(14, 16, 20, 0.16);

  width: 250px;

  & div.type-display {
    font-weight: 600;

    padding: 10px;
    margin-bottom: 10px;
    border-bottom: 1px solid ${globals.MOON_250};
  }

  & ul.items-list {
    margin: 0px;
    list-style: none;
    padding: 0 6px 6px 6px;
    max-height: 250px;
    overflow-y: scroll;
    overflow-x: hidden;

    &::-webkit-scrollbar {
      width: 6px;
    }
    &::-webkit-scrollbar-track,
    &::-webkit-scrollbar-track:hover {
      background-color: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background-color: #666;
      border-radius: 3px;
    }
  }

  & ul.items-list li.${SUGGESTION_OPTION_CLASS} {
    white-space: nowrap;
    cursor: pointer;
    text-overflow: ellipsis;
    overflow: hidden;
    padding-left: 5px;

    &.default-suggestion {
      background-color: ${globals.MOON_100};
    }
  }
`;
SuggestionPane.displayName = 'S.SuggestionPane';

export const SuggestionCategory = styled.li`
  color: ${globals.MOON_800};
  font-family: Source Sans Pro;
  font-size: 16px;
  font-style: normal;
  font-weight: 600;
  line-height: 20px;
  padding: 8px 4px;
`;
SuggestionCategory.displayName = 'S.SuggestionCategory';

export const StyledOpDoc = styled(OpDoc)`
  display: inline-block;
  max-width: 400px;
  vertical-align: top;
  margin-left: 5px;

  color: ${globals.WHITE};
  background-color: ${globals.MOON_900};
  padding: 12px;
  border-radius: 4px;
  box-shadow: 0px 12px 24px 0px rgba(14, 16, 20, 0.16);

  & a {
    color: ${globals.TEAL_500};

    &:hover {
      color: ${globals.TEAL_450};
    }
  }
`;
StyledOpDoc.displayName = 'S.StyledOpDoc';
