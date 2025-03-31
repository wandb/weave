import {foundations} from '@wandb/ui';
import {WBIcon} from '@wandb/ui';
import styled from 'styled-components';

import type {WBMenuTheme} from './WBMenu';

const {legacy} = foundations;

type ContentProps = {
  width?: number;
  backgroundColor?: string;
  dataTest?: string;
};
export const Content = styled.div.attrs((props: ContentProps) => ({
  'data-test': props.dataTest || 'wb-menu',
}))<ContentProps>`
  width: ${props => (props.width ? props.width + 'px' : 'fit-content')};
  padding: 8px 0;
  background: ${props =>
    props.backgroundColor ?? getBGForTheme(props.theme.main)};
  border-radius: 6px;
  box-shadow: ${legacy.boxShadowDropdown};
`;

export const Item = styled.div<{
  hovered?: boolean;
  fontSize?: number;
  lineHeight?: number;
}>`
  color: ${props => getTextForTheme(props.theme.main)};
  padding: 8px 16px 8px 16px;
  font-size: ${props => props.fontSize ?? 14}px;
  line-height: ${props => props.lineHeight ?? 16}px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  word-break: break-word;
  background: ${props =>
    props.hovered ? getHighlightForTheme(props.theme.main) : 'none'};
`;

export const ItemIcon: typeof WBIcon = styled(WBIcon)`
  margin-left: 8px;
  font-size: 16px;
  width: 16px;
  flex-shrink: 0;
`;

type Colors = {
  background: string;
  highlight: string;
  text: string;
};

const THEME_COLORS: {[t in WBMenuTheme]: Colors} = {
  dark: {
    background: legacy.darkerGray,
    highlight: legacy.primary,
    text: legacy.white,
  },
  light: {
    background: legacy.white,
    highlight: legacy.gray100,
    text: legacy.gray800,
  },
};

function getBGForTheme(t: WBMenuTheme): string {
  return THEME_COLORS[t].background;
}
function getHighlightForTheme(t: WBMenuTheme): string {
  return THEME_COLORS[t].highlight;
}
function getTextForTheme(t: WBMenuTheme): string {
  return THEME_COLORS[t].text;
}
