import {WBIcon} from '@wandb/ui';
import {Icon} from '@wandb/weave/components/Icon';
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

export const StyledIcon = styled(WBIcon)<{
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

export const ProtectedAliasIcon = styled(Icon)<{
  size: keyof typeof IconVariants;
  $pos: string;
  $opacity?: number;
  $cursor?: string;
}>`
  ${props => IconVariants[props.size]};
  margin: 2px 2px 2px 2px;
  ${props =>
    props.$pos === 'left' ? `margin-left: -4px;` : `margin-right: -4px;`}
  opacity: ${props => props.$opacity};
  ${props => (props.$cursor ? `cursor: ${props.$cursor};` : '')}
`;
