import React, {useMemo} from 'react';

import {parseRef} from '../../../../../../react';
import {parseRefMaybe, SmallRef} from '../../../Browse2/SmallRef';
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

  return <div>{data.value.toString()}</div>;
};
