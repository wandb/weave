import StrippedContentEditable from '@wandb/weave/common/components/StrippedContentEditable';
import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

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

export const PanelNameSpan = styled.span`
  text-transform: capitalize;
  display: flex;
  align-items: center;
`;

export const InlineContentEditable = styled(StrippedContentEditable)<{
  disabled?: boolean;
}>`
  margin: 0;
  padding: 0 2px;
  line-height: 20px;
  border-radius: 2px;
  min-width: 2px;
  outline: none;
  display: inline-block;
  position: relative;
  &:hover {
    background: ${props => (props.disabled ? 'none' : props.theme.focused)};
  }
  &:focus {
    background: ${props => props.theme.clickable};
    box-shadow: 0 0 0 1px ${props => props.theme.focused} !important;
  }
`;
