import * as globals from '@wandb/weave/common/css/globals.styles';
import styled, {css} from 'styled-components';

export const IconButton = styled.div<{small?: boolean}>`
  ${p =>
    !p.small &&
    css`
      width: 24px;
      height: 24px;
    `}
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;

  svg {
    width: 18px;
    height: 18px;
  }

  color: ${globals.GRAY_500};
  &:hover {
    color: ${globals.GRAY_600};
    background-color: ${globals.GRAY_50};
  }

  &:not(:last-child) {
    margin-right: 4px;
  }
`;
