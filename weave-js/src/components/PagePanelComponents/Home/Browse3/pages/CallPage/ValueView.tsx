import React from 'react';

import {parseRef} from '../../../../../../react';
import {SmallRef} from '../../../Browse2/SmallRef';
import {WANDB_ARTIFACT_REF_PREFIX} from '../wfReactInterface/constants';
import {ValueViewNumber} from './ValueViewNumber';
import {ValueViewPrimitive} from './ValueViewPrimitive';
import {ValueViewString} from './ValueViewString';

type ValueData = Record<string, any>;

type ValueViewProps = {
  data: ValueData;
  isExpanded: boolean;
};

export const isRef = (value: any): boolean => {
  return (
    typeof value === 'string' && value.startsWith(WANDB_ARTIFACT_REF_PREFIX)
  );
};

export const ValueView = ({data, isExpanded}: ValueViewProps) => {
  if (!data.isLeaf) {
    if (data.valueType === 'object' && '_ref' in data.value) {
      return <SmallRef objRef={parseRef(data.value._ref)} />;
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
