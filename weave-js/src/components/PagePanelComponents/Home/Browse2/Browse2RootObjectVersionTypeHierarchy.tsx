import {useNodeValue} from '@wandb/weave/react';
import React, {FC, useMemo} from 'react';

import {
  Type,
  callOpVeryUnsafe,
  constString,
  isObjectType,
  isSimpleTypeShape,
} from '../../../../core';

const typeName = (t: Type) => {
  if (isSimpleTypeShape(t)) {
    return t;
  } else {
    return t.type;
  }
};

export const Browse2RootObjectVersionTypeHierarchy: FC<{uri: string}> = ({
  uri,
}) => {
  const refTypeNode = useMemo(() => {
    const refNode = callOpVeryUnsafe('ref', {uri: constString(uri)});
    return callOpVeryUnsafe('Ref-type', {ref: refNode});
  }, [uri]);

  const refTypeQuery = useNodeValue(refTypeNode as any);
  const hierarchy = useMemo(() => {
    const hierarchy: Type[] = [];
    let currentType = refTypeQuery.result as null | Type;
    while (currentType) {
      hierarchy.push(currentType);
      if (isObjectType(currentType) && currentType._base_type) {
        currentType = currentType._base_type;
      } else {
        currentType = null;
      }
    }
    return hierarchy.reverse();
  }, [refTypeQuery]);

  return (
    <ul>
      {hierarchy.map((t, i) => (
        <li key={i} style={{marginLeft: i * 16}}>
          {typeName(t)}
        </li>
      ))}
    </ul>
  );
};
