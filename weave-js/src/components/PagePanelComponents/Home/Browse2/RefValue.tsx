import {objectRefWithExtra, parseRef, refUri} from '@wandb/weave/react';
import React, {useMemo} from 'react';

import {isListLike, isObjectTypeLike, isTypedDictLike} from '../../../../core';
import {isRef} from '../Browse3/pages/common/util';
import {
  DICT_KEY_EDGE_TYPE,
  LIST_INDEX_EDGE_TYPE,
  OBJECT_ATTRIBUTE_EDGE_TYPE,
} from '../Browse3/pages/wfReactInterface/constants';
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
  const {
    derived: {useRefsType},
  } = useWFHooks();
  const getRefsType = useRefsType([weaveRef]);
  if (getRefsType.loading || getRefsType.result == null) {
    return <></>;
  } else if (isTypedDictLike(getRefsType.result[0])) {
    return (
      <RefValueWithExtra
        weaveRef={weaveRef}
        attribute={DICT_KEY_EDGE_TYPE + '/' + attribute}
      />
    );
  } else if (isObjectTypeLike(getRefsType.result[0])) {
    return (
      <RefValueWithExtra
        weaveRef={weaveRef}
        attribute={OBJECT_ATTRIBUTE_EDGE_TYPE + '/' + attribute}
      />
    );
  } else if (isListLike(getRefsType.result[0])) {
    return (
      <RefValueWithExtra
        weaveRef={weaveRef}
        attribute={LIST_INDEX_EDGE_TYPE + '/' + attribute}
      />
    );
  }
  return <>Unknown Type</>;
};

const RefValueWithExtra = ({weaveRef, attribute}: RefValueProps) => {
  const {useRefsData} = useWFHooks();
  const objRef = parseRef(weaveRef);
  const objRefWithExtra = useMemo(() => {
    return objectRefWithExtra(objRef, attribute);
  }, [attribute, objRef]);
  const refValue = useRefsData([refUri(objRefWithExtra)]);

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
