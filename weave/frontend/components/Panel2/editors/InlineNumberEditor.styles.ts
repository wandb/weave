import styled from 'styled-components';
import NumberContentEditable from '../NumberContentEditable';

export const InlineNumberContentEditable = styled(NumberContentEditable)`
  background: ${props => props.theme.clickable};
  margin: 0;
  padding: 0 2px;
  line-height: 20px;
  border-radius: 2px;
  min-width: 2px;
  outline: none;
  display: inline-block;
  position: relative;
  &:hover {
    background: ${props => props.theme.focused};
  }
  &:focus {
    background: ${props => props.theme.clickable};
    box-shadow: 0 0 0 1px ${props => props.theme.focused} !important;
  }
`;
