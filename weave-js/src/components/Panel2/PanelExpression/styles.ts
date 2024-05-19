import * as globals from '@wandb/weave/common/css/globals.styles';
import {Button} from 'semantic-ui-react';
import styled, {css, keyframes} from 'styled-components';

export const Main = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
`;
Main.displayName = 'S.Main';

export const EditorBar = styled.div`
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
`;
EditorBar.displayName = 'S.EditorBar';

export const LockToggleButton = styled.div`
  padding-left: 4px;
  &:hover {
    cursor: pointer;
    background-color: ${globals.gray200} !important;
  }
`;
LockToggleButton.displayName = 'S.LockToggleButton';

export const BarButton = styled(Button)`
  margin-right: -5px !important;
  padding: 5px !important;
  background: none !important;
  border: none !important;
  transition-property: border, background-color !important;
  transition-duration: 0.2s !important;

  &:hover {
    background-color: ${globals.gray200} !important;
  }
  & > i {
    margin: 0 !important;
  }
`;
BarButton.displayName = 'S.BarButton';

export const ConfigButton = styled(Button)`
  margin-right: -5px !important;
  padding: 5px !important;
  background: none !important;
  border: none !important;
  transition-property: border, background-color !important;
  transition-duration: 0.2s !important;

  &:hover {
    background-color: ${globals.gray200} !important;
  }
`;
ConfigButton.displayName = 'S.ConfigButton';

const rotate = keyframes`
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
`;

export const PanelHandler = styled.div<{lazySusan?: boolean}>`
  flex: 1 1 auto;
  display: flex;
  overflow: hidden;

  ${p =>
    p.lazySusan &&
    css`
      border-radius: 50%;
      animation: ${rotate} 20s linear infinite;
    `}
`;
PanelHandler.displayName = 'S.PanelHandler';

export const PanelHandlerContent = styled.div`
  flex: 1 1 auto;
  overflow: auto;
`;
PanelHandlerContent.displayName = 'S.PanelHandlerContent';

export const PanelHandlerConfig = styled.div`
  flex: 0 0 350px;
  padding-left: 10px;
  margin-left: 10px;
  margin-top: 10px;
  border-left: 1px solid #eee;
`;
PanelHandlerConfig.displayName = 'S.PanelHandlerConfig';

export const ConfigurationContent = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
`;
ConfigurationContent.displayName = 'S.ConfigurationContent';

export const ConfigurationContentItems = styled.div`
  flex: 1 1 auto;
  overflow-x: hide;
  overflow-y: visible;
`;
ConfigurationContentItems.displayName = 'S.ConfigurationContentItems';

export const ConfigurationContentItem = styled.div`
  height: 100%;
  width: 100%;
`;
ConfigurationContentItem.displayName = 'S.ConfigurationContentItem';

export const ConfigurationContentControls = styled.div`
  flex: 0 0 auto;
  height: 35px;
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
`;
ConfigurationContentControls.displayName = 'S.ConfigurationContentControls';

export const SidebarWrapper = styled.div`
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.2);
  z-index: 100;
`;
SidebarWrapper.displayName = 'S.SidebarWrapper';
