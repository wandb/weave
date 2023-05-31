import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const IconButton = styled.div`
  display: flex;
  color: ${globals.GRAY_500};

  svg {
    width: 18px;
    height: 18px;
  }
`;
