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
AdvancedPropertiesHeader.displayName = 'S.AdvancedPropertiesHeader';

export const ConstrainedIconContainer = styled.div`
  height: 24px;
  display: flex;
  padding: 3px;
  justify-content: center;
  align-items: center;
  background-color: ${globals.TEAL_TRANSPARENT};
  color: ${globals.TEAL};
  border-radius: 4px;
  margin-left: 8px;
  cursor: pointer;
  &:hover {
    background-color: ${globals.TEAL_LIGHT_TRANSPARENT};
  }
`;
ConstrainedIconContainer.displayName = 'S.ConstrainedIconContainer';

export const UnconstrainedIconContainer = styled.div`
  height: 24px;
  display: flex;
  padding: 3px;
  color: ${globals.MOON_500};
  justify-content: center;
  align-items: center;
  border-radius: 4px;
  margin-left: 8px;
  cursor: pointer;
  &:hover {
    background-color: ${globals.MOON_100};
  }
`;
UnconstrainedIconContainer.displayName = 'S.UnconstrainedIconContainer';
