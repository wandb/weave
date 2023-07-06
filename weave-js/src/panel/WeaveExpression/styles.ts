import * as globals from '@wandb/weave/common/css/globals.styles';
import {Button} from 'semantic-ui-react';
import {Editable} from 'slate-react';
import styled, {css} from 'styled-components';

import OpDoc from './OpDoc';

export const EditableContainer = styled.div<{
  noBox?: boolean;
  isInvalid?: boolean;
}>`
  position: relative;
  display: flex;
  flex: 1 1 auto;

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
    `}
`;

export const WeaveEditable = styled(Editable)<{$truncate?: boolean}>`
  width: 100%;
  min-height: 20px;
  line-height: 20px;

  font-family: Inconsolata;
  cursor: text;

  // Req'd to make editor selectable in Safari
  user-select: text;

  &.invalid {
    border-bottom: 1px dotted ${globals.RED};
  }

  & span.identifier {
    color: ${globals.MAGENTA};
  }

  span.property_identifier {
    color: ${globals.SIENNA_DARK};
  }

  & span.operator {
    color: ${globals.SIENNA_DARK};
  }

  & span.string {
    color: ${globals.TEAL};
  }

  & span.number,
  & span.null {
    color: ${globals.TEAL};
  }

  & span.boolean {
    color: ${globals.TEAL};
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

export const ApplyButton = styled(Button)`
  display: none;
  position: absolute;
  font-size: 13px !important;
  line-height: 20px !important;
  padding: 0px 4px !important;
  height: 20px;
`;

export const SuggestionContainer = styled.div`
  position: absolute;
  top: -10000px;
  left: -10000px;
  z-index: 2147483647;

  transition: opacity 0.3s;
  opacity: 0;
`;
export const SUGGESTION_OPTION_CLASS = 'suggestion-option';
export const SuggestionPane = styled.div<{isBusy: boolean}>`
  background-color: rgba(0, 0, 0, 0.9);
  color: #ddd;
  display: inline-block;

  padding: 10px;
  border-radius: 3px;
  width: 250px;

  & div.type-display {
    font-weight: 600;

    padding-bottom: 10px;
    margin-bottom: 10px;
    border-bottom: 2px solid #666;
  }

  & ul.items-list {
    margin: 0px;
    list-style: none;
    padding: 0px;
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
      background-color: rgba(255, 255, 255, 0.2);
      padding-right: 30px;
    }

    &.default-suggestion:before {
      color: ${props => (props.isBusy ? globals.gray500 : globals.primary)};
      text-align: right;
      content: '⇥';
      float: right;
      margin-right: -25px;
    }

    &:hover {
      background-color: rgba(255, 255, 255, 0.2);
    }
  }
`;

export const StyledOpDoc = styled(OpDoc)`
  display: inline-block;
  vertical-align: top;
  margin-left: 5px;

  background-color: #fffeee;
  padding: 10px;
  border-radius: 3px;
  border: 1px solid black;

  max-width: 250px;
`;
