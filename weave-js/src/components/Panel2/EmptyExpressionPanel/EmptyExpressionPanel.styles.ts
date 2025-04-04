import {STRING_COLOR} from '@wandb/weave/panel/WeaveExpression/styles';
import styled, {css} from 'styled-components';

import {Icon} from '../../Icon';

const COLORS = {
  teal: '#13a9ba',
  text: {
    dark: '#333',
    medium: '#666',
  },
  border: '#e1e1e1',
  hover: '#f8f8f8',
  dropdown: {
    bg: 'rgb(250, 250, 250)',
    itemHover: '#f1f1f1',
  },
};

const SPACING = {
  xs: '2px',
  sm: '4px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  xxl: '24px',
};

const FONTS = {
  code: 'Inconsolata',
  sizes: {
    xs: '0.75em',
    sm: '0.8em',
    md: '1em',
  },
};

const flexCenter = css`
  display: flex;
  align-items: center;
  justify-content: center;
`;

const cardBase = css`
  padding: ${SPACING.xl};
  border-radius: 8px;
  border: 1px solid ${COLORS.border};
  background-color: #ffffff;
  transition: all 0.2s ease-in-out;
  box-sizing: border-box;
  width: min(100%, 300px);
  margin: 0 auto;
  position: relative;
`;

export const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
  position: relative;
  padding: 2px;
  box-sizing: border-box;
  container-type: inline-size; /* Enable container queries */
`;

export const HeaderSection = styled.div`
  padding-top: ${SPACING.lg};
  text-align: center;
  flex-shrink: 0;
  padding-bottom: ${SPACING.xs};
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 2;
  background-color: white;
  min-height: min-content;
  width: 100%;
`;

export const Title = styled.p`
  font-size: ${FONTS.sizes.md};
  font-weight: 650;
  color: ${COLORS.text.dark};
  margin: ${SPACING.md} 0;
`;

export const Subtitle = styled.p`
  font-size: ${FONTS.sizes.xs};
  color: ${COLORS.text.dark};
  margin: 0;
`;

export const ScrollableContainer = styled.div`
  flex: 1 1 auto;
  overflow-x: hidden;
  width: 100%;
  padding: 0 ${SPACING.xxl} ${SPACING.xxl};
  box-sizing: border-box;
  position: relative;
  padding-top: ${SPACING.xs};
  transition: max-height 0.2s ease-out;
  will-change: max-height;

  // Scrollbar styling
  &::-webkit-scrollbar {
    width: 6px;
    display: block;
  }
  &::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 8px;
  }
  &::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 8px;

    &:hover {
      background: #a1a1a1;
    }
  }

  /* Firefox */
  scrollbar-width: thin;
  scrollbar-color: #c1c1c1 #f1f1f1;
`;

// Dynamically sized scrollable container with overflow protection
export const DynamicScrollContainer = styled(ScrollableContainer)<{
  headerHeight: number;
  shouldScroll: boolean;
  isInitialized: boolean;
}>`
  flex: 1 1 auto;
  max-height: ${props =>
    props.isInitialized ? `calc(100% - ${props.headerHeight}px)` : '0px'};
  overflow-y: ${props => (props.shouldScroll ? 'auto' : 'visible')};
  visibility: ${props => (props.isInitialized ? 'visible' : 'hidden')};
  transition: max-height 0.2s ease-out;
`;

export const CardGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr));
  gap: ${SPACING.lg};
  width: 100%;
  box-sizing: border-box;
  margin-top: ${SPACING.lg};
  padding-bottom: ${SPACING.xxl};
  padding-top: ${SPACING.sm};
  height: fit-content;
  overflow: visible;
  justify-items: center;
  align-items: start;
`;

export const Card = styled.div`
  ${cardBase}
  display: flex;
  flex-direction: column;
  justify-content: start;
  align-items: flex-start;
  align-content: center;
  cursor: pointer;
  z-index: 1;
  transform-origin: center center;
  margin-top: ${SPACING.xs};

  &:hover {
    border-color: ${COLORS.teal};
    z-index: 2;
  }
`;

export const CardTitleContainer = styled.div`
  display: flex;
  align-items: center;
  gap: ${SPACING.md};
`;

export const CardTitle = styled.div`
  margin: 0;
  font-size: ${FONTS.sizes.xs};
  font-weight: 400;
  text-align: center;
`;

export const CardSubtitle = styled.span`
  padding-top: ${SPACING.xs};
  font-family: ${FONTS.code};
`;

export const ExpressionWrapper = styled.div`
  display: flex;
  align-items: baseline;
  color: ${COLORS.text.medium};
  font-size: ${FONTS.sizes.sm};
  line-height: 1;
  flex-wrap: wrap;

  .bracket-group-container {
    display: inline-flex;
    align-items: baseline;
    margin: 0;
    padding: 0;
  }

  @container (max-width: 230px) {
    &.pickcard-expression {
      display: grid;
      grid-template-columns: auto;
      gap: ${SPACING.xs};
    }
  }
`;

export const BracketGroup = styled.div.attrs({
  className: 'bracket-group-container',
})`
  && {
    display: inline-flex;
    align-items: baseline;
    margin: 0;
    padding: 0;
  }
`;

export const StyledDropdownWrapper = styled.div`
  margin: 0 ${SPACING.xs};
  display: flex;
  align-content: center;

  .ui.dropdown {
    color: ${STRING_COLOR} !important;
    border: none;
    background: transparent;
    box-shadow: none;
    border-radius: 3px;
    padding: 0;
    display: flex;
    align-content: center;
    min-height: 0;
    min-width: 48px;

    .default.text {
      color: ${STRING_COLOR} !important;
    }

    > .dropdown.icon {
      display: none;
    }

    .menu {
      border-radius: 3px;
      margin-top: ${SPACING.xs};
      min-width: 100px;
      width: auto;
      max-height: 120px;

      > .item {
        font-size: ${FONTS.sizes.md};
        padding: ${SPACING.md} ${SPACING.lg} !important;
        border-bottom: 1px solid #f0f0f0;
        color: ${STRING_COLOR} !important;
        white-space: nowrap;
        background-color: #ffffff !important;

        &:hover {
          background-color: ${COLORS.dropdown.itemHover} !important;
        }
      }

      > .item.selected {
        background-color: ${COLORS.dropdown.itemHover} !important;
      }
    }

    input.search {
      padding: 0 !important;
    }
  }

  .ui.active.dropdown {
    border-color: transparent !important;
    box-shadow: none !important;
  }
`;

export const SearchIconContainer = styled.div`
  ${flexCenter}
  height: 36px;
  width: 36px;
  aspect-ratio: 1;

  @container (max-width: 200px) {
    height: 32px;
    width: 32px;
  }

  @container (max-width: 150px) {
    height: 28px;
    width: 28px;
  }
`;

export const SearchIcon = styled(Icon)`
  height: 50%;
  width: 50%;
  flex: none;
`;
