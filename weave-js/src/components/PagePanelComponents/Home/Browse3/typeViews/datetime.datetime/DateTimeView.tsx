import React from 'react';

import {CellValueTimestamp} from '../../../Browse2/CellValueTimestamp';
type DateTimeViewProps = {
  data: {
    val: string;
  };
};

export const DateTimeView = ({data}: DateTimeViewProps) => {
  return <CellValueTimestamp value={data.val} />;
};
