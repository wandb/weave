import React, {ReactNode} from 'react';
import styled from 'styled-components';

import {
  MOON_100,
  MOON_150,
  MOON_200,
} from '../../../../../../common/css/color.styles';
import {Tooltip} from '../../../../../Tooltip';
import {getBoringColumns, TableStats} from '../../../Browse2/tableStats';
import {BoringStringValue} from './BoringStringValue';

type BoringColumnInfoProps = {
  tableStats: TableStats;
  columns: any;
};

const Boring = styled.div`
  overflow: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
`;
Boring.displayName = 'S.Boring';

const Header = styled.div`
  white-space: nowrap;
  padding: 4px;
  font-weight: 600;
`;
Header.displayName = 'S.Header';

const BoringPair = styled.div`
  display: flex;
  align-items: center;
  align-content: stretch;
`;
BoringPair.displayName = 'S.BoringPair';

const BoringLabel = styled.div`
  background-color: ${MOON_150};
  padding: 4px 8px;
  border-right: 1px solid ${MOON_200};
  border-radius: 8px 0 0 8px;
`;
BoringLabel.displayName = 'S.BoringLabel';

const BoringValue = styled.div`
  background-color: ${MOON_100};
  padding: 4px 8px;
  border-radius: 0 8px 8px 0;
  max-width: 300px;
  display: flex;
  align-items: center;
`;
BoringValue.displayName = 'S.BoringValue';

export const BoringColumnInfo = ({
  tableStats,
  columns,
}: BoringColumnInfoProps) => {
  const boring = getBoringColumns(tableStats);

  const boringPairs = boring
    .map((colName: string) => {
      const {valueCounts} = tableStats.column[colName];
      const boringValue = Object.keys(valueCounts)[0];
      if (boringValue === 'null') {
        return null;
      }

      const col = columns.find((c: any) => c.field === colName);
      if (!col) {
        return null;
      }

      let label = col.field;
      if (!label.includes('.') && col.headerName) {
        label = col.headerName;
      }

      let value: ReactNode = boringValue;
      let height: number | undefined = 32;
      if (col.renderCell) {
        const cellParams = {value, row: {[col.field]: value}};
        value = col.renderCell(cellParams);
        if (typeof value === 'string') {
          value = (
            <BoringStringValue
              value={value}
              maxWidthCollapsed={300}
              maxWidthExpanded={600}
            />
          );
          height = undefined;
        }
      }

      return (
        <BoringPair key={colName}>
          <BoringLabel>{label}</BoringLabel>
          <BoringValue style={{height}}>{value}</BoringValue>
        </BoringPair>
      );
    })
    .filter(pair => pair !== null);

  if (boringPairs.length === 0) {
    return null;
  }

  return (
    <Boring>
      <Tooltip
        content="These columns have the same value for every row"
        trigger={<Header>Common values:</Header>}
      />
      {boringPairs}
    </Boring>
  );
};
