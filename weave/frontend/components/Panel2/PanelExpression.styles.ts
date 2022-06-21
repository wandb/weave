import styled, {css, keyframes} from 'styled-components';
import * as globals from '@wandb/common/css/globals.styles';
import {Button} from 'semantic-ui-react';

export const Main = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
`;

export const EditorBar = styled.div`
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
`;

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

export const PanelHandlerContent = styled.div`
  flex: 1 1 auto;
  overflow: hidden;
`;

export const PanelHandlerConfig = styled.div`
  flex: 0 0 350px;
  padding-left: 10px;
  margin-left: 10px;
  margin-top: 10px;
  border-left: 1px solid #eee;
`;

export const ConfigurationContent = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 400px;
`;

export const ConfigurationContentItems = styled.div`
  flex: 1 1 auto;
  overflow-x: hide;
  overflow-y: visible;
`;

export const ConfigurationContentItem = styled.div`
  width: 100%;
`;

export const ConfigurationContentControls = styled.div`
  flex: 0 0 auto;
  height: 35px;
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
`;
