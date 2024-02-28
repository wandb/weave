import React from 'react';
import styled from 'styled-components';

import {MOON_150} from '../../../../../../common/css/color.styles';
import {parseRef} from '../../../../../../react';
import {SmallRef} from '../../../Browse2/SmallRef';
import {WANDB_ARTIFACT_REF_PREFIX} from '../wfReactInterface/constants';
import {ValueViewNumber} from './ValueViewNumber';
import {ValueViewString} from './ValueViewString';

type ValueData = Record<string, any>;

type ValueViewProps = {
  data: ValueData;
  isExpanded: boolean;
};

export const Primitive = styled.div`
  display: inline-block;
  padding: 0 4px;
  background-color: ${MOON_150};
  border-radius: 4px;
  font-weight: 600;
  font-family: monospace;
  font-size: 10px;
  line-height: 20px;
`;
Primitive.displayName = 'S.Primitive';

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
    return <Primitive>null</Primitive>;
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
    return <Primitive>{data.value.toString()}</Primitive>;
  }

  return <div>{data.value.toString()}</div>;
};
