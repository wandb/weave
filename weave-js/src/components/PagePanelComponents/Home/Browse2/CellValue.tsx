import {Box} from '@mui/material';
import React from 'react';

import {parseRef} from '../../../../react';
import {isWeaveRef} from '../Browse3/filters/common';
import {ValueViewNumber} from '../Browse3/pages/CallPage/ValueViewNumber';
import {
  isProbablyTimestamp,
  ValueViewNumberTimestamp,
} from '../Browse3/pages/CallPage/ValueViewNumberTimestamp';
import {ValueViewPrimitive} from '../Browse3/pages/CallPage/ValueViewPrimitive';
import {isCustomWeaveTypePayload} from '../Browse3/typeViews/customWeaveType.types';
import {CustomWeaveTypeDispatcher} from '../Browse3/typeViews/CustomWeaveTypeDispatcher';
import {CellValueBoolean} from './CellValueBoolean';
import {CellValueImage} from './CellValueImage';
import {CellValueString} from './CellValueString';
import {SmallRef} from './SmallRef';

type CellValueProps = {
  value: any;
};

export const CellValue = ({value}: CellValueProps) => {
  if (value === undefined) {
    return null;
  }
  if (value === null) {
    return <ValueViewPrimitive>null</ValueViewPrimitive>;
  }
  if (isWeaveRef(value)) {
    return <SmallRef objRef={parseRef(value)} />;
  }
  if (typeof value === 'boolean') {
    return (
      <Box
        sx={{
          textAlign: 'center',
          width: '100%',
        }}>
        <CellValueBoolean value={value} />
      </Box>
    );
  }
  if (typeof value === 'string') {
    if (value.startsWith('data:image/')) {
      return <CellValueImage value={value} />;
    }
    return <CellValueString value={value} />;
  }
  if (typeof value === 'number') {
    if (isProbablyTimestamp(value)) {
      return <ValueViewNumberTimestamp value={value} />;
    }
    return (
      <Box
        sx={{
          textAlign: 'right',
          width: '100%',
        }}>
        <ValueViewNumber value={value} fractionDigits={4} />
      </Box>
    );
  }
  if (isCustomWeaveTypePayload(value)) {
    return <CustomWeaveTypeDispatcher data={value} />;
  }
  return <CellValueString value={JSON.stringify(value)} />;
};
