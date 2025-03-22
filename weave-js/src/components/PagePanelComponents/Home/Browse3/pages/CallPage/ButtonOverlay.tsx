/**
 * This makes part of the UI work more like a button.
 */

import React, {ReactNode} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {WHITE} from '../../../../../../common/css/color.styles';
import {hexToRGB} from '../../../../../../common/css/utils';
import {Button} from '../../../../../Button';

type ButtonOverlayProps = {
  url: string;
  text: string;
  children: ReactNode;
};

const Container = styled.div`
  cursor: pointer;
  position: relative;
  height: 100%;
`;
Container.displayName = 'S.Container';

const ChildWrapper = styled.div`
  user-select: none;
  pointer-events: none;
  position: absolute;
  inset: 0;
`;
ChildWrapper.displayName = 'S.ChildWrapper';

const Overlay = styled.div`
  z-index: 1; // Unfortunate, but necessary to appear over the MUI data grid header
  position: absolute;
  background-color: ${hexToRGB(WHITE, 0.7)};
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s ease-in-out 0s;
  &:hover {
    opacity: 1;
  }
`;
Overlay.displayName = 'S.Overlay';

const OverlayMessage = styled.div`
  padding: 8px;
  background-color: ${WHITE};
`;
OverlayMessage.displayName = 'S.OverlayMessage';

export const ButtonOverlay = ({url, text, children}: ButtonOverlayProps) => {
  const history = useHistory();
  const onClick = () => {
    const currentUrl = new URL(window.location.href);
    const currentCols = currentUrl.searchParams.get('cols');

    // Get the target URL from baseRouter
    const targetUrl = new URL(url, window.location.origin);

    // If we have current column visibility state, add it to the target URL
    if (currentCols) {
      targetUrl.searchParams.set('cols', currentCols);
    }

    history.push(targetUrl.pathname + targetUrl.search);
  };
  return (
    <Container onClick={onClick}>
      <ChildWrapper>{children}</ChildWrapper>
      <Overlay>
        <OverlayMessage>
          <Button variant="ghost" icon="share-export" active={true}>
            {text}
          </Button>
        </OverlayMessage>
      </Overlay>
    </Container>
  );
};
