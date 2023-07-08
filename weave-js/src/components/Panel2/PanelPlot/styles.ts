import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const AdvancedPropertiesHeader = styled.div`
  color: ${globals.TEAL_DARK};
  cursor: pointer;
  height: 36px;
  line-height: 36px;
  font-weight: 600;
  &:hover {
    color: ${globals.TEAL_LIGHT};
  }
`;
