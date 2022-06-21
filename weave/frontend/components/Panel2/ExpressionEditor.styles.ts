import * as globals from '@wandb/common/css/globals.styles';

import styled, {css} from 'styled-components';
import {IconButton} from '@material-ui/core';
import OpDoc from './OpDoc';

export const themes = {
  light: {
    // Not sure if any of these are used
    popupBackground: globals.white,
    popupHover: '#f6f8f8',
    popupBorder: '#ccc',
    indenter: '#dadada',
    background: '#fafafa',
    text: '#1a1a1a',
    delete: '#777',

    // background color used to show clickable elements
    clickable: '#f6f6f6',

    // used for background on both hover and focus
    focused: '#eaeaea',

    // panel names
    panelName: '#56acfc',

    // note we could differentiate between node types, like const string
    // v const number if we want.
    node: '#008a4b',

    // function names
    op: '#9D624C',

    // function names
    panelOp: '#56acfc',
  },
};

export const ExpressionEditor = styled.span`
  font-family: Inconsolata;
`;

export const ExpressionEditorWrapper = styled.div<{
  noBox?: boolean;
  isInvalid?: boolean;
  showPlainText?: boolean;
}>`
  cursor: text;
  position: relative;
  display: flex;
  width: 100%;
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

  .raw-input-toggle {
    visibility: ${({showPlainText}) => (showPlainText ? 'visible' : 'hidden')};
  }

  &:hover .raw-input-toggle {
    visibility: visible;
  }
`;

export const ExpressionEditorContainer = styled.span`
  cursor: text;
  flex: 1 1 auto;
`;

export const OpWrapper = styled.span<{error?: boolean}>`
  border-radius: 2px;
  ${props =>
    props.error &&
    css`
      background: rgba(237, 101, 90, 0.6);
      border: 1px solid rgb(237, 101, 90);
    `}
`;

export const ExpressionEditorContextMenu = styled.div`
  margin: 0;
  padding: 0;
  list-style-type: none;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: center;
`;

export const ExpressionEditorContextMenuItem = styled.div`
  display: inline;
  flex: 0 0 auto;
`;

export const ExpressionEditorContextMenuButton = styled(IconButton)`
  /* padding: 5px; */
`;

export const ExpressionEditorPlainTextContainer = styled.div`
  flex: 1 0 auto;
  padding-right: 1px;
`;

type ExpressionEditorPlainTextTextareaProps = {
  error: boolean;
};
export const ExpressionEditorPlainTextInput = styled.input<ExpressionEditorPlainTextTextareaProps>`
  resize: none;
  width: 100%;
  border-radius: 3px;
  border: ${({error}) => (error ? 'red 1px solid' : 'lightgray 1px solid')};
  font-family: monospace !important;
  height: 30px;
  line-height: 30px;
  padding: 0px 5px;
  font-size: 15px;

  &:focus-visible {
    border: ${({error}) => (error ? 'red 1px solid' : 'lightgray 1px solid')};
    outline: none;
  }
`;

export const ExpressionEditorTypeDisplay = styled.div`
  transition: opacity 0.2s;
  position: absolute;
  z-index: 1000;
  background-color: #222;
  color: #ddd;
  border-radius: 6px;
  padding: 8px;
  font-size: 13px;
  margin-top: 5px;

  &:hover {
    opacity: 0.25;
  }
`;

export const ToastIconContainer = styled.span`
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  background-color: #f9f9f9;
  color: rgba(0, 0, 0, 0.54);
  border-radius: 2px;
`;

export const VarName = styled.span`
  color: #d44c1c;
`;

export const ElementSpan = styled.span`
  color: ${(props: {theme: any; elementType: 'node' | 'op' | 'panelOp'}) =>
    props.theme[props.elementType]};
`;

export const PanelNameSpan = styled.span`
  text-transform: capitalize;
  color: ${props => props.theme.panelName};
`;

export const OpDocCard = styled(OpDoc).attrs(
  ({isAutocomplete}: {isAutocomplete?: boolean}) => ({
    isAutocomplete,
  })
)`
  background-color: ${globals.gray200};
  border: 1px solid ${globals.gray500};
  padding: 4px 8px 0 8px;
  border-radius: 6px;

  ${props =>
    props.isAutocomplete
      ? css`
          border-top-left-radius: 0px;
        `
      : null}
`;
