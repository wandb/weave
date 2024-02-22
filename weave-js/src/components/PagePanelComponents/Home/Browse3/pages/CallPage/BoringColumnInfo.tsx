import React from 'react';
import styled from 'styled-components';

import {
  MOON_100,
  MOON_150,
  MOON_200,
} from '../../../../../../common/css/color.styles';
import {Tooltip} from '../../../../../Tooltip';
import {getBoringColumns, TableStats} from '../../../Browse2/tableStats';

type BoringColumnInfoProps = {
  tableStats: TableStats;
  columns: any;
};

const Boring = styled.div`
  display: flex;
  flex-wrap: wrap;
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
  height: 32px;
  display: flex;
  align-items: center;
  background-color: ${MOON_100};
  padding: 4px 8px;
  border-radius: 0 8px 8px 0;
`;
BoringValue.displayName = 'S.BoringValue';

export const BoringColumnInfo = ({
  tableStats,
  columns,
}: BoringColumnInfoProps) => {
  const boring = getBoringColumns(tableStats);
  if (boring.length === 0) {
    return null;
  }
  return (
    <Boring>
      <Tooltip
        content="These columns have the same value for every row"
        trigger={<Header>Common values:</Header>}
      />
      {boring.map((colName: string) => {
        const {valueCounts} = tableStats.column[colName];
        const boringValue = Object.keys(valueCounts)[0];
        if (boringValue === 'null') {
          return null;
        }

        const col = columns.find((c: any) => c.field === colName);

        let label = col.field;
        if (!label.includes('.') && col.headerName) {
          label = col.headerName;
        }

        let value = boringValue;
        if (col.renderCell) {
          const cellParams = {value, row: {[col.field]: value}};
          value = col.renderCell(cellParams);
        }

        return (
          <BoringPair key={colName}>
            <BoringLabel>{label}</BoringLabel>
            <BoringValue>{value}</BoringValue>
          </BoringPair>
        );
      })}
    </Boring>
  );
};
