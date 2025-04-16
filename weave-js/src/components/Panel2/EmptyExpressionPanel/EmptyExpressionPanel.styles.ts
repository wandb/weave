import styled, {css} from 'styled-components';

const COLORS = {
  teal: '#13a9ba',
  text: {
    primary: '#2B3038',
    secondary: '#565C66',
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
  normal: 'Source Sans Pro',
};

const cardBase = css`
  padding: ${SPACING.lg};
  border-radius: 8px;
  border: 1px solid ${COLORS.border};
  background-color: #ffffff;
  transition: all 0.2s ease-in-out;
  box-sizing: border-box;
  width: 100%;
  margin: 0;
  position: relative;
`;

export const Container = styled.div`
  display: flex;
  flex-direction: column;

  max-height: 90%;
  overflow: hidden;
  position: relative;
  padding: ${SPACING.xs};
  box-sizing: border-box;
  container-type: inline-size; /* Enable container queries */
`;

export const HeaderSection = styled.div`
  font-family: ${FONTS.normal};
  font-size: 14px;
  padding-top: ${SPACING.lg};
  text-align: center;
  padding-bottom: ${SPACING.xs};
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  margin-bottom: ${SPACING.md};
`;

export const Title = styled.p`
  font-weight: 600;
  color: ${COLORS.text.primary};
`;

export const Subtitle = styled.p`
  color: ${COLORS.text.secondary};
  margin: 0;
`;

export const ScrollableContainer = styled.div`
  flex: 1 1 auto;
  overflow-x: hidden;
  width: 100%;
  padding: 0 ${SPACING.md} ${SPACING.md};
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
  padding: 0 ${SPACING.xxl} ${SPACING.xxl};
  padding-top: ${SPACING.xs};
`;

export const CardGrid = styled.div`
  display: grid;
  gap: ${SPACING.md};
  width: 100%;
  max-width: 900px; /* Prevent the grid from becoming too wide */
  margin: ${SPACING.lg} auto 0;
  padding-bottom: ${SPACING.md};
  padding-top: ${SPACING.xs};
  height: fit-content;
  overflow: visible;
  justify-content: start;
  align-items: stretch;
`;

export const Card = styled.div`
  ${cardBase}
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-start;
  cursor: pointer;
  z-index: 1;
  padding: ${SPACING.sm} ${SPACING.md};

  &:hover {
    border-color: ${COLORS.teal};
    z-index: 2;
  }
`;

export const CardTitleContainer = styled.div`
  display: flex;
  align-items: center;
  gap: ${SPACING.md};
  width: 100%;
`;

export const CardTitle = styled.div`
  font-family: ${FONTS.normal};
  margin: 0;
  color: ${COLORS.text.primary};
  font-size: 14px;
  font-weight: 400;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
  min-width: 0; /* Allow element to shrink */
`;

export const CardSubtitle = styled.span`
  padding-top: ${SPACING.sm};
  font-family: ${FONTS.code};
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
`;

export const ExpressionWrapper = styled.div`
  display: flex;
  align-items: baseline;
  color: ${COLORS.text.secondary};
  font-size: 14px;
  line-height: 1;
  flex-wrap: wrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
`;
