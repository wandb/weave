import {Box} from '@mui/material';
import React from 'react';
import styled from 'styled-components';

import {parseRef} from '../../../../react';
import {ValueViewNumber} from '../Browse3/pages/CallPage/ValueViewNumber';
import {ValueViewPrimitive} from '../Browse3/pages/CallPage/ValueViewPrimitive';
import {isRef} from '../Browse3/pages/common/util';
import {isCustomWeaveTypePayload} from '../Browse3/typeViews/customWeaveType.types';
import {CustomWeaveTypeDispatcher} from '../Browse3/typeViews/CustomWeaveTypeDispatcher';
import {CellValueBoolean} from './CellValueBoolean';
import {CellValueImage} from './CellValueImage';
import {CellValueString} from './CellValueString';
import {SmallRef} from './SmallRef';

type CellValueProps = {
  value: any;
  isExpanded?: boolean;
};

const Collapsed = styled.div<{hasScrolling: boolean}>`
  min-height: 38px;
  line-height: 38px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: ${props => (props.hasScrolling ? 'pointer' : 'default')};
`;
Collapsed.displayName = 'S.Collapsed';

export const CellValue = ({value, isExpanded = false}: CellValueProps) => {
  if (value === undefined) {
    return null;
  }
  if (value === null) {
    return <ValueViewPrimitive>null</ValueViewPrimitive>;
  }
  if (isRef(value)) {
    return <SmallRef objRef={parseRef(value)} iconOnly={isExpanded} />;
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
