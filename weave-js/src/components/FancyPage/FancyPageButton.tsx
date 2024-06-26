import {MEDIUM_BREAKPOINT} from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const SidebarButton = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
`;
SidebarButton.displayName = 'S.SidebarButton';

export const MenuButton = styled(SidebarButton)`
  cursor: pointer;
`;
MenuButton.displayName = 'S.MenuButton';

type ItemIconProps = {
  color: string;
};
export const ItemIcon = styled.div<ItemIconProps>`
  height: 32px;
  box-sizing: border-box;
  border-radius: 8px;
  padding: 6px 12px;
  background-color: ${props => props.color};
  display: flex;
  align-items: center;
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    padding: 0 12px;
  }
`;
ItemIcon.displayName = 'S.ItemIcon';

type ItemLabelProps = {
  color: string;
};
export const ItemLabel = styled.div<ItemLabelProps>`
  color: ${props => props.color};
  font-family: 'Source Sans Pro';
  font-weight: 600;
  height: 14px;
  font-size: 10px;
  line-height: 14px;
  text-align: center;
`;
ItemLabel.displayName = 'S.ItemLabel';
