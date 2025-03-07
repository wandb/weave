import React from 'react';
import styled from 'styled-components';

import {CellValueTimestamp} from '../../../Browse2/CellValueTimestamp';
type DateTimeViewProps = {
  data: {
    val: string;
  };
};

const DateTime = styled.div`
  cursor: pointer;
`;
DateTime.displayName = 'S.DateTime';

export const DateTimeView = ({data}: DateTimeViewProps) => {
  return <CellValueTimestamp value={data.val} />;
};
