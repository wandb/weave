import styled from 'styled-components';
import StrippedContentEditable from '@wandb/common/components/StrippedContentEditable';

export const InlineContentEditable = styled(StrippedContentEditable)<{
  disabled?: boolean;
}>`
  background: ${props => (props.disabled ? 'none' : props.theme.clickable)};
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
