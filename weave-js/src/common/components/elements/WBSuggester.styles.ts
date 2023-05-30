import styled, {css} from 'styled-components';

import {GLOBAL_COLORS} from '../../util/colors';
import {WBAnchoredPopup} from '../WBAnchoredPopup';
import WBQueryMenu from './WBQueryMenu';

export const SuggestionMenuPopup = styled(WBAnchoredPopup)`
  border-radius: 4px;
  transform: translateY(2px);
`;

export const SuggestionPopupFlexWrapper = styled.div`
  display: flex;
  flex-direction: row;
  align-items: start;
`;

type SuggestionMenuProps = {
  $maxHeight: number;
};

export const SuggestionMenu = styled(WBQueryMenu)<SuggestionMenuProps>`
  flex: 0 0 auto;

  ${props =>
    css`
      max-height: ${props.$maxHeight}px;
    `}

  overflow-y: scroll;
  scrollbar-width: none; // firefox

  /* force the menu to draw over the context panel */
  z-index: 1;

  &::-webkit-scrollbar {
    width: 0;
    height: 0;
  }
`;

export const SuggestionContext = styled.div`
  flex: 0 0 auto;
  position: relative;
  left: -4px;
`;

export const Option = styled.div<{hovered?: boolean}>`
  color: white;
  padding: 8px 16px 8px 16px;
  font-size: 14px;
  line-height: 16px;
  cursor: pointer;
  background: ${props =>
    props.hovered ? GLOBAL_COLORS.primary.toString() : 'none'};
`;
