import styled from 'styled-components';
import * as globals from '@wandb/weave/common/css/globals.styles';

export const ObjectCount = styled.div`
  color: ${globals.MOON_500};
  font-family: Source Sans Pro;
  font-size: 14px;
  font-style: normal;
  font-weight: 600;
  text-transform: uppercase;
`;
ObjectCount.displayName = 'S.ObjectCount';
