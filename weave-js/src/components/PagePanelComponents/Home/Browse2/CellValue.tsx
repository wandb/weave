import {Box} from '@mui/material';
import React from 'react';

import {parseRef} from '../../../../react';
import {isArtifactRef, isWeaveRef} from '../Browse3/filters/common';
import {ValueViewNumber} from '../Browse3/pages/CallPage/ValueViewNumber';
import {
  isProbablyTimestamp,
  ValueViewNumberTimestamp,
} from '../Browse3/pages/CallPage/ValueViewNumberTimestamp';
import {ValueViewPrimitive} from '../Browse3/pages/CallPage/ValueViewPrimitive';
import {SmallRef} from '../Browse3/smallRef/SmallRef';
import {isCustomWeaveTypePayload} from '../Browse3/typeViews/customWeaveType.types';
import {CustomWeaveTypeDispatcher} from '../Browse3/typeViews/CustomWeaveTypeDispatcher';
import {CellValueBoolean} from './CellValueBoolean';
import {CellValueImage} from './CellValueImage';
import {CellValueString} from './CellValueString';

type CellValueProps = {
  value: any;
  noLink?: boolean;
  /** Optional style overrides for string values */
  stringStyle?: React.CSSProperties;
  field?: string;
};

export const CellValue = ({
  value,
  noLink,
  stringStyle,
  field,
}: CellValueProps) => {
  if (value === undefined) {
    return null;
  }
  if (value === null) {
    return <ValueViewPrimitive>null</ValueViewPrimitive>;
  }
  if (isWeaveRef(value) || isArtifactRef(value)) {
    return <SmallRef objRef={parseRef(value)} noLink={noLink} />;
  }
  if (typeof value === 'boolean') {
    return (
      <Box
        sx={{
          textAlign: 'center',
          width: '100%',
          height: '100%',
        }}>
        <CellValueBoolean value={value} />
      </Box>
    );
  }
  if (typeof value === 'string') {
    if (value.startsWith('data:image/')) {
      return <CellValueImage value={value} />;
    }
    return <CellValueString value={value} style={stringStyle} />;
  }
  if (typeof value === 'number') {
    if (field && isProbablyTimestamp(value, field)) {
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
