import {WBIcon} from '@wandb/ui';
import styled, {css} from 'styled-components';

const IconVariants = {
  small: css`
    font-size: 12px;
  `,
  medium: css`
    font-size: 14px;
  `,
  large: css`
    font-size: 16px;
  `,
};

export const Icon = styled(WBIcon)<{
  size: keyof typeof IconVariants;
  $pos: string;
  $opacity?: number;
  $cursor?: string;
}>`
  ${props => IconVariants[props.size]};
  margin: 4px 4px 4px 4px;
  ${props =>
    props.$pos === 'left' ? `margin-left: -4px;` : `margin-right: -4px;`}
  display: flex;
  align-items: center;
  opacity: ${props => props.$opacity};
  ${props => (props.$cursor ? `cursor: ${props.$cursor};` : '')}
`;
