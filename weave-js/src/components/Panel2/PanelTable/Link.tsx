import {
  TEAL_400,
  TEAL_450,
  TEAL_550,
  TEAL_600,
} from '@wandb/weave/common/css/color.styles';
import styled from 'styled-components';

export const Link = styled.a.attrs(props => ({
  className: `night-aware ${props.className ?? ''}`,
}))`
  font-weight: 600;
  color: ${TEAL_600};
  .night-mode & {
    color: ${TEAL_450};
  }
  &:hover {
    color: ${TEAL_550};
  }
  .night-mode &:hover {
    color: ${TEAL_400};
  }
`;
Link.displayName = 'Link';
