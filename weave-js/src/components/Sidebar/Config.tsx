import {
  GRAY_350,
  GRAY_500,
  SCROLLBAR_STYLES,
} from '@wandb/weave/common/css/globals.styles';
import styled, {css} from 'styled-components';

export const Container = styled.div`
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
`;

export const Header = styled.div`
  padding: 12px 0;
  border-bottom: 1px solid ${GRAY_350};
`;

export const HeaderTop = styled.div<{lessLeftPad?: boolean}>`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 8px 0 ${p => (p.lessLeftPad ? 8 : 12)}px;
`;

export const HeaderTopLeft = styled.div<{canGoBack?: boolean}>`
  display: flex;
  align-items: center;
  ${p =>
    p.canGoBack &&
    css`
      color: ${GRAY_500};
      cursor: pointer;
    `}
`;

export const HeaderTopRight = styled.div`
  display: flex;
  align-items: center;
`;

export const HeaderTopText = styled.div`
  font-weight: 600;
`;

export const HeaderTitle = styled.div`
  font-family: 'Inconsolata', monospace;
  font-size: 18px;
  font-weight: 600;
  margin-top: 8px;
  padding: 0 12px;
`;

export const Body = styled.div`
  flex-grow: 1;
  overflow-x: hidden;
  overflow-y: auto;
  ${SCROLLBAR_STYLES}
`;
