/**
 * This is similar to ValueView or CellValue - it dispatches
 * to the appropriate component for rendering based on the value type.
 */
import React from 'react';

import {maybePluralizeWord} from '../../../../../core/util/string';
import {parseRef} from '../../../../../react';
import {UserLink} from '../../../../UserLink';
import {ObjectPath} from '../pages/CallPage/traverse';
import {ValueViewNumber} from '../pages/CallPage/ValueViewNumber';
import {
  isProbablyTimestampMs,
  isProbablyTimestampSec,
} from '../pages/CallPage/ValueViewNumberTimestamp';
import {ValueViewPrimitive} from '../pages/CallPage/ValueViewPrimitive';
import {SmallRef} from '../smallRef/SmallRef';
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
    const objSize = Object.keys(value).length;
    return (
      <div className="flex items-center gap-4">
        <ValueViewPrimitive>object</ValueViewPrimitive>{' '}
        <span>
          {objSize.toLocaleString()} {maybePluralizeWord(objSize, 'key')}
        </span>
      </div>
    );
  }
  if (valueType === 'array') {
    const arrSize = value.length;
    return (
      <div className="flex items-center gap-4">
        <ValueViewPrimitive>array</ValueViewPrimitive>{' '}
        <span>
          {arrSize.toLocaleString()} {maybePluralizeWord(arrSize, 'item')}
        </span>
      </div>
    );
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

  if (valueType === 'boolean') {
    return <ValueViewPrimitive>{value.toString()}</ValueViewPrimitive>;
  }

  return <div>{value}</div>;
};
