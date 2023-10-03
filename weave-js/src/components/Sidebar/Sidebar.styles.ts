import * as globals from '@wandb/weave/common/css/globals.styles';
import {GLOBAL_COLORS} from '@wandb/weave/common/util/colors';
import {Button} from 'semantic-ui-react';
import styled from 'styled-components';

export const Wrapper = styled.div<{collapsed: boolean; width: number}>`
  height: 100vh;
  width: ${props => (props.collapsed ? 0 : props.width)}px;
  background: white;
  position: sticky;
  top: 0;
  border-left: 1px solid ${GLOBAL_COLORS.outline.toString()};
  z-index: 100;
  display: flex;
  font-size: 14px;
  line-height: 20px;
  flex-direction: column;
`;

export const Title = styled.div`
  padding: 2.25px 4px 2.25px 16px;
  line-height: 20px;
  display: flex;
  justify-content: flex-end;
`;

export const Main = styled.div`
  flex-grow: 1;
  overflow: hidden;
`;

export const PropertyEditorWrapper = styled.div`
  padding: 6px 16px;
`;

export const InspectorPropertyWrapper = styled.div`
  display: flex;
  align-items: center;
  position: relative;
`;

export const InspectorPropertyLabel = styled.div`
  width: 100px;
  color: #888;
`;

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
