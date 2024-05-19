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
  padding: 3px;
  border-radius: 3px;

  color: ${globals.MOON_500};
  &:hover {
    color: ${globals.MOON_800};
    background-color: ${globals.hexToRGB(globals.OBLIVION, 0.05)};
  }

  &:not(:last-child) {
    margin-right: 4px;
  }
`;
