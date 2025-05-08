import {Icon} from '@wandb/weave/components/Icon';
import styled, {css} from 'styled-components';

const IconVariants = {
  small: css`
    width: 12px;
    height: 12px;
  `,
  medium: css`
    width: 14px;
    height: 14px;
  `,
  large: css`
    width: 16px;
    height: 16px;
  `,
};

export const StyledIcon = styled(Icon)<{
  size: keyof typeof IconVariants;
  $pos: string;
  $opacity?: number;
  $cursor?: string;
}>`
  ${props => IconVariants[props.size]};
  margin: auto 4px;
  ${props =>
    props.$pos === 'left' ? `margin-left: -4px;` : `margin-right: -4px;`}
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  opacity: ${props => props.$opacity};
  ${props => (props.$cursor ? `cursor: ${props.$cursor};` : '')}
`;
