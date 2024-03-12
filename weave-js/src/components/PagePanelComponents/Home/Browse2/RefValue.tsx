import {objectRefWithExtra, parseRef, refUri} from '@wandb/weave/react';
import React, {useMemo} from 'react';

import {isRef} from '../Browse3/pages/common/util';
import {OBJECT_ATTRIBUTE_EDGE_TYPE} from '../Browse3/pages/wfReactInterface/constants';
import {useWFHooks} from '../Browse3/pages/wfReactInterface/context';
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

const RENDER_DIRECTLY = new Set([
  typeof 0,
  typeof '',
  typeof true,
  typeof false,
]);

export const RefValue = ({weaveRef, attribute}: RefValueProps) => {
  const {useRefsData} = useWFHooks();
  const objRef = parseRef(weaveRef);
  const objRefWithExtra = useMemo(() => {
    return objectRefWithExtra(
      objRef,
      OBJECT_ATTRIBUTE_EDGE_TYPE + '/' + attribute
    );
  }, [attribute, objRef]);
  const refValue = useRefsData(
    useMemo(() => [refUri(objRefWithExtra)], [objRefWithExtra])
  );

  if (refValue.loading) {
    return <>loading...</>;
  }

  if (refValue.result == null || refValue.result.length === 0) {
    console.error('RefValueTypeChecked: no result', weaveRef);
    return <NotApplicable />;
  }

  const refData = refValue.result[0];

  if (isRef(refData)) {
    return <SmallRef objRef={parseRef(refData)} />;
  } else if (RENDER_DIRECTLY.has(typeof refData)) {
    return <CellValue value={refData} />;
  } else {
    return <SmallRef objRef={objRefWithExtra} />;
  }
};
