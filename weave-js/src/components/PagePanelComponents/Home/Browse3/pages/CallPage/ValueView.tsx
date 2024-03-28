import React, {useMemo} from 'react';

import {parseRef} from '../../../../../../react';
import {parseRefMaybe, SmallRef} from '../../../Browse2/SmallRef';
import {WeaveCHTable} from '../../../Browse2/WeaveEditors';
import {TableView} from '../../dataViews/TableView';
import {isRef} from '../common/util';
import {ValueViewNumber} from './ValueViewNumber';
import {ValueViewPrimitive} from './ValueViewPrimitive';
import {ValueViewString} from './ValueViewString';

type ValueData = Record<string, any>;

type ValueViewProps = {
  data: ValueData;
  isExpanded: boolean;
  baseRef?: string;
};

export const ValueView = ({data, isExpanded, baseRef}: ValueViewProps) => {
  const opDefRef = useMemo(() => parseRefMaybe(data.value ?? ''), [data.value]);
  if (!data.isLeaf) {
    if (data.valueType === 'object' && '_ref' in data.value) {
      return <SmallRef objRef={parseRef(data.value._ref)} />;
    }
    if (data.valueType === 'array') {
      return (
        // <Box
        //   style={{
        //     // minHeight: '400px',
        //     // maxHeight: '400px',
        //     width: '100%',
        //     overflow: 'hidden',
        //   }}>
        <TableView data={data.value} />
        // </Box>
      );
    }
    console.log(data);
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
      console.log(data);
      return (
        <WeaveCHTable
          tableRefUri={data.value}
          path={data.path.path}
          baseRef={baseRef}
        />
      );
    }
    return <SmallRef objRef={parseRef(data.value)} />;
  }

  if (data.valueType === 'string') {
    return <ValueViewString value={data.value} isExpanded={isExpanded} />;
  }

  if (data.valueType === 'number') {
    return <ValueViewNumber value={data.value} />;
  }

  if (data.valueType === 'boolean') {
    return <ValueViewPrimitive>{data.value.toString()}</ValueViewPrimitive>;
  }

  return <div>{data.value.toString()}</div>;
};
