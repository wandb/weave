import {constString, opGet} from '@wandb/weave/core';
import {
  parseRef,
  useNodeValue,
  useNodeWithServerType,
} from '@wandb/weave/react';
import React from 'react';

import {CellValue} from './CellValue';
import {NotApplicable} from './NotApplicable';
import {SmallRef} from './SmallRef';

type RefValueProps = {
  // There are unfortunate name collisions:
  // React ref and Weave ref
  // React key and object key
  weaveRef: string;
  attribute: string;
};

const RefValueTypeChecked = ({weaveRef, attribute}: RefValueProps) => {
  let valueUrl = weaveRef;
  if (attribute !== 'propertyTypes') {
    valueUrl += `#atr/${attribute}`;
  }
  const valueNode = opGet({uri: constString(valueUrl)});
  const query = useNodeValue(valueNode);
  if (query.loading) {
    return <>loading...</>;
  }
  return <CellValue value={query.result} />;
};

const RENDER_DIRECTLY = new Set(['none', 'string']);

export const RefValue = ({weaveRef, attribute}: RefValueProps) => {
  const refNode = opGet({uri: constString(weaveRef)});
  const refNodeTyped = useNodeWithServerType(refNode);
  if (refNodeTyped.loading) {
    return <>loading...</>;
  }
  const refType = refNodeTyped.result.type as any;
  if (typeof refType === 'string') {
    return <>TODO</>;
  } else if (attribute in refType) {
    const attributeType = refType[attribute];
    if (RENDER_DIRECTLY.has(attributeType) || attribute === 'propertyTypes') {
      return <RefValueTypeChecked weaveRef={weaveRef} attribute={attribute} />;
    }
    const valueUrl = `${weaveRef}#atr/${attribute}`;
    return <SmallRef objRef={parseRef(valueUrl)} />;
  }
  return <NotApplicable />;
};
