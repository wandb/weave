import {useNodeValue} from '@wandb/weave/react';
import React, {FC, useMemo} from 'react';
import {Link, useParams} from 'react-router-dom';

import {
  callOpVeryUnsafe,
  constString,
  isObjectType,
  isSimpleTypeShape,
  Type,
} from '../../../../core';
import {useWeaveflowRouteContext} from '../Browse3/context';
import {typeIdFromTypeVersion} from '../Browse3/pages/interface/dataModel';

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
  const params = useParams<{entity: string; project: string}>();
  const refTypeNode = useMemo(() => {
    const refNode = callOpVeryUnsafe('ref', {uri: constString(uri)});
    return callOpVeryUnsafe('Ref-type', {ref: refNode});
  }, [uri]);

  const refTypeQuery = useNodeValue(refTypeNode as any);

  const hierarchy = useMemo(() => {
    const typeHierarchy: Type[] = [];
    let currentType = refTypeQuery.result as null | Type;
    while (currentType) {
      typeHierarchy.push(currentType);
      if (isObjectType(currentType) && currentType._base_type) {
        currentType = currentType._base_type;
      } else {
        currentType = null;
      }
    }
    return typeHierarchy.reverse();
  }, [refTypeQuery]);
  const urls = useWeaveflowRouteContext();
  return (
    <ul>
      {hierarchy.map((t, i) => (
        <li key={i} style={{marginLeft: i * 16}}>
          <Link
            to={urls.typeVersionUIUrl(
              params.entity,
              params.project,
              typeName(t),
              typeIdFromTypeVersion(t)
            )}>
            {typeName(t)}:{typeIdFromTypeVersion(t)}
          </Link>
        </li>
      ))}
    </ul>
  );
};
