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

export const ConstrainedIconContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: ${globals.TEAL_TRANSPARENT};
  color: ${globals.TEAL};
  padding: 3px;
  border-radius: 3px;
`;

export const UnconstrainedIconContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 3px;
  border-radius: 3px;
`;
