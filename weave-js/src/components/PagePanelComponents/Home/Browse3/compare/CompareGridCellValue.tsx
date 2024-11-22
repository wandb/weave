/**
 * This is similar to ValueView or CellValue - it dispatches
 * to the appropriate component for rendering based on the value type.
 */
import React from 'react';

import {parseRef} from '../../../../../react';
import {UserLink} from '../../../../UserLink';
import {SmallRef} from '../../Browse2/SmallRef';
import {ObjectPath} from '../pages/CallPage/traverse';
import {ValueViewNumber} from '../pages/CallPage/ValueViewNumber';
import {
  isProbablyTimestampMs,
  isProbablyTimestampSec,
} from '../pages/CallPage/ValueViewNumberTimestamp';
import {ValueViewPrimitive} from '../pages/CallPage/ValueViewPrimitive';
import {MISSING} from './compare';
import {CompareGridCellValueCode} from './CompareGridCellValueCode';
import {CompareGridCellValueTimestamp} from './CompareGridCellValueTimestamp';
import {RESOLVED_REF_KEY} from './refUtil';

type CompareGridCellValueProps = {
  path: ObjectPath;
  value: any;
  valueType: any;
};

export const CompareGridCellValue = ({
  path,
  value,
  valueType,
}: CompareGridCellValueProps) => {
  if (value === MISSING) {
    return <ValueViewPrimitive>missing</ValueViewPrimitive>;
  }
  if (value === undefined) {
    return <ValueViewPrimitive>undefined</ValueViewPrimitive>;
  }
  if (value === null) {
    return <ValueViewPrimitive>null</ValueViewPrimitive>;
  }
  if (path.toString() === 'wb_user_id') {
    return <UserLink userId={value} includeName />;
  }
  if (valueType === 'code') {
    return <CompareGridCellValueCode value={value} />;
  }
  if (valueType === 'object') {
    if (RESOLVED_REF_KEY in value) {
      return <SmallRef objRef={parseRef(value[RESOLVED_REF_KEY])} />;
    }
    // We don't need to show anything for this row because user can expand it to compare child keys
    return null;
  }
  if (valueType === 'array') {
    return <ValueViewPrimitive>array</ValueViewPrimitive>;
  }

  if (valueType === 'number') {
    if (isProbablyTimestampSec(value)) {
      return <CompareGridCellValueTimestamp value={value} unit="s" />;
    }
    if (isProbablyTimestampMs(value)) {
      return <CompareGridCellValueTimestamp value={value} unit="ms" />;
    }
    return <ValueViewNumber value={value} />;
  }

  return <div>{value}</div>;
};
