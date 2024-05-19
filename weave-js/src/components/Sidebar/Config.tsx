import {
  GRAY_350,
  SCROLLBAR_STYLES,
} from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const Container = styled.div`
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
`;
Container.displayName = 'S.Container';

export const Header = styled.div`
  padding: 12px 0;
  border-bottom: 1px solid ${GRAY_350};
`;
Header.displayName = 'S.Header';

export const HeaderTop = styled.div<{lessLeftPad?: boolean}>`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 8px 0 ${p => (p.lessLeftPad ? 8 : 12)}px;
`;
HeaderTop.displayName = 'S.HeaderTop';

export const HeaderTopLeft = styled.div`
  display: flex;
  align-items: center;
`;
HeaderTopLeft.displayName = 'S.HeaderTopLeft';

export const HeaderTopRight = styled.div`
  display: flex;
  align-items: center;
`;
HeaderTopRight.displayName = 'S.HeaderTopRight';

export const HeaderTopText = styled.div`
  font-weight: 600;
`;
HeaderTopText.displayName = 'S.HeaderTopText';

export const HeaderTitle = styled.div`
  font-family: 'Inconsolata', monospace;
  font-size: 18px;
  font-weight: 600;
  margin-top: 8px;
  padding: 0 12px;
`;
HeaderTitle.displayName = 'S.HeaderTitle';

export const Body = styled.div`
  flex-grow: 1;
  overflow-x: hidden;
  overflow-y: auto;
  ${SCROLLBAR_STYLES}
`;
Body.displayName = 'S.Body';
