import {MOON_450} from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const PanelSettings = styled.div`
  padding: 8px 24px;
  background-color: #f6f6f6;
  border-radius: 4px;
  // min-width: 600px;
  :empty {
    padding: 0;
  }
  overflow: visible;
  // max-height: 300px;
`;

export const FacetGridWrapper = styled.div<{
  hasXAxisLabel: boolean;
  hasYAxisLabel: boolean;
}>`
  display: grid;
  width: 100%;
  height: 100%;
  grid-template-columns: ${({hasYAxisLabel}) => (hasYAxisLabel ? '24px' : '')} 40px repeat(
      auto-fit,
      minmax(0, 1fr)
    );
  grid-template-rows: ${({hasXAxisLabel}) => (hasXAxisLabel ? '24px' : '')} 40px repeat(
      auto-fit,
      minmax(0, 1fr)
    );
  padding: 8px;
`;

export const xAxisLabel = styled.div<{
  columnCount: number;
  hasYAxisLabel: boolean;
}>`
  grid-column-end: ${({columnCount}) => columnCount};
  grid-row-start: 1;
  grid-column-start: ${({hasYAxisLabel}) => (hasYAxisLabel ? 3 : 2)};
  display: flex;
  justify-content: center;
  height: 24px;
`;

export const yAxisLabel = styled.div<{
  rowCount: number;
  hasXAxisLabel: boolean;
}>`
  grid-row-end: ${({rowCount}) => rowCount};
  grid-row-start: ${({hasXAxisLabel}) => (hasXAxisLabel ? 3 : 2)};
  grid-column-start: 1;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  writing-mode: vertical-rl;
  rotate: 180deg;
`;

export const FacetHeaderCell = styled.div<{
  gridRowStart: number;
  gridColumnStart: number;
}>`
  grid-row-start: ${({gridRowStart}) => gridRowStart};
  grid-column-start: ${({gridColumnStart}) => gridColumnStart};
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 14px;
  color: ${MOON_450};
`;
