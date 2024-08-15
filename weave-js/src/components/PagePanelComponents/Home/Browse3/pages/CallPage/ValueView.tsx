import React, {useMemo} from 'react';

import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {parseRefMaybe, SmallRef} from '../../../Browse2/SmallRef';
import {isCustomWeaveTypePayload} from '../../typeViews/customWeaveType.types';
import {CustomWeaveTypeDispatcher} from '../../typeViews/CustomWeaveTypeDispatcher';
import {isRef} from '../common/util';
import {
  DataTableView,
  USE_TABLE_FOR_ARRAYS,
  WeaveCHTable,
} from './DataTableView';
import {ValueViewImage} from './ValueViewImage';
import {ValueViewNumber} from './ValueViewNumber';
import {
  isProbablyTimestamp,
  ValueViewNumberTimestamp,
} from './ValueViewNumberTimestamp';
import {ValueViewPrimitive} from './ValueViewPrimitive';
import {ValueViewString} from './ValueViewString';

type ValueData = Record<string, any>;

type ValueViewProps = {
  data: ValueData;
  isExpanded: boolean;
};

export const ValueView = ({data, isExpanded}: ValueViewProps) => {
  const opDefRef = useMemo(() => parseRefMaybe(data.value ?? ''), [data.value]);
  if (!data.isLeaf) {
    if (data.valueType === 'object' && '_ref' in data.value) {
      return <SmallRef objRef={parseRef(data.value._ref)} />;
    }
    if (USE_TABLE_FOR_ARRAYS && data.valueType === 'array') {
      return <DataTableView data={data.value} />;
    }
    return null;
  }

  if (data.value === undefined) {
    return null;
  }
  if (data.value === null) {
    return <ValueViewPrimitive>null</ValueViewPrimitive>;
  }
  if (isRef(data.value)) {
    if (
      opDefRef &&
      opDefRef.scheme === 'weave' &&
      opDefRef.weaveKind === 'table'
    ) {
      return <WeaveCHTable tableRefUri={data.value} />;
    }
    return <SmallRef objRef={parseRef(data.value)} />;
  }

  if (data.valueType === 'string') {
    if (data.value.startsWith('data:image/')) {
      return <ValueViewImage value={data.value} />;
    }
    return <ValueViewString value={data.value} isExpanded={isExpanded} />;
  }

  if (data.valueType === 'number') {
    if (isProbablyTimestamp(data.value)) {
      return <ValueViewNumberTimestamp value={data.value} />;
    }
    return <ValueViewNumber value={data.value} />;
  }

  if (data.valueType === 'boolean') {
    return <ValueViewPrimitive>{data.value.toString()}</ValueViewPrimitive>;
  }

  if (data.valueType === 'array') {
    // Compared to toString this keeps the square brackets.
    // This is particularly helpful for empty lists, for which toString would return an empty string.
    return <div>{JSON.stringify(data.value)}</div>;
  }

  if (data.valueType === 'object') {
    if (isCustomWeaveTypePayload(data.value)) {
      // This is a little ugly, but essentially if the data is coming from an
      // expanded ref, then we want to use that ref to get the entity and project.
      // Else we just use the current entity and project.
      let entityForWeaveType: string | undefined;
      let projectForWeaveType: string | undefined;

      if (valueIsExpandedRef(data)) {
        const parsedRef = parseRef((data.value as any)._ref);
        if (isWeaveObjectRef(parsedRef)) {
          entityForWeaveType = parsedRef.entityName;
          projectForWeaveType = parsedRef.projectName;
        }
      }

      // If we have have a custom view for this weave type, use it.
      return (
        <CustomWeaveTypeDispatcher
          data={data.value}
          entity={entityForWeaveType}
          project={projectForWeaveType}
        />
      );
    }
  }

  return <div>{data.value.toString()}</div>;
};

const valueIsExpandedRef = (data: ValueData) => {
  return data.value != null && (data.value as any)._ref != null;
};
