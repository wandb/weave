import {getTypeName, Type} from '@wandb/weave/core';
import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  ObjectRef,
  refUri,
  WeaveObjectRef,
} from '@wandb/weave/react';
import React, {FC} from 'react';

import {IconName, IconNames} from '../../../../Icon';
import {useWeaveflowRouteContext} from '../context';
import {Link} from '../pages/common/Links';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {isObjDeleteError} from '../pages/wfReactInterface/utilities';
import {
  ObjectVersionKey,
  OpVersionKey,
} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallRefBox} from './SmallRefBox';
import {WFDBTableType} from './types';

const getRootType = (t: Type): Type => {
  if (
    (t as any)._base_type != null &&
    (t as any)._base_type?.type !== 'Object'
  ) {
    return getRootType((t as any)._base_type);
  }
  return t;
};

export const objectRefDisplayName = (
  objRef: ObjectRef,
  versionIndex?: number
) => {
  if (isWandbArtifactRef(objRef)) {
    const versionStr =
      versionIndex != null
        ? `v${versionIndex}`
        : objRef.artifactVersion.slice(0, 6);
    let label = `${objRef.artifactName}:${versionStr}`;
    if (objRef.artifactPath !== 'obj') {
      label += '/' + objRef.artifactPath;
    }
    if (objRef.artifactRefExtra) {
      // Remove every other extra part
      const parts = objRef.artifactRefExtra.split('/');
      const newParts = [];
      for (let i = 1; i < parts.length; i += 2) {
        newParts.push(parts[i]);
      }
      label += '#' + newParts.join('/');
    }
    return {label};
  } else if (isWeaveObjectRef(objRef)) {
    const versionStr =
      versionIndex != null
        ? `v${versionIndex}`
        : objRef.artifactVersion.slice(0, 6);
    let label = `${objRef.artifactName}:${versionStr}`;
    if (objRef.artifactRefExtra) {
      label += '/' + objRef.artifactRefExtra;
    }
    return {label};
  }
  throw new Error('Unknown ref type');
};

export const SmallWeaveRef: FC<{
  objRef: WeaveObjectRef;
  wfTable?: WFDBTableType;
  iconOnly?: boolean;
}> = ({objRef, wfTable, iconOnly = false}) => {
  const {
    useObjectVersion,
    useOpVersion,
    derived: {useRefsType},
  } = useWFHooks();

  let objVersionKey: ObjectVersionKey | null = null;
  let opVersionKey: OpVersionKey | null = null;

  if (objRef.weaveKind === 'op') {
    opVersionKey = {
      entity: objRef.entityName,
      project: objRef.projectName,
      opId: objRef.artifactName,
      versionHash: objRef.artifactVersion,
    };
  } else {
    objVersionKey = {
      scheme: 'weave',
      entity: objRef.entityName,
      project: objRef.projectName,
      weaveKind: objRef.weaveKind,
      objectId: objRef.artifactName,
      versionHash: objRef.artifactVersion,
      path: '',
      refExtra: objRef.artifactRefExtra,
    };
  }

  const objectVersion = useObjectVersion(objVersionKey, true);
  const opVersion = useOpVersion(opVersionKey, true);
  const isDeleted =
    isObjDeleteError(objectVersion?.error) ||
    isObjDeleteError(opVersion?.error);
  const versionIndex =
    objectVersion.result?.versionIndex ?? opVersion.result?.versionIndex;

  const {peekingRouter} = useWeaveflowRouteContext();
  const refTypeQuery = useRefsType([refUri(objRef)]);
  const refType: Type =
    refTypeQuery.loading || refTypeQuery.result == null
      ? 'unknown'
      : refTypeQuery.result[0];
  let rootType = getRootType(refType);
  if (objRef.scheme === 'weave' && objRef.weaveKind === 'op') {
    // TODO: Why is this necessary? The type is coming back as `objRef`
    rootType = {type: 'OpDef'};
  }
  const {label} = objectRefDisplayName(objRef, versionIndex);

  const rootTypeName = getTypeName(rootType);
  let icon: IconName = IconNames.CubeContainer;
  if (rootTypeName === 'Dataset') {
    icon = IconNames.Table;
  } else if (rootTypeName === 'Model') {
    icon = IconNames.Model;
  } else if (rootTypeName === 'List') {
    icon = IconNames.List;
  } else if (rootTypeName === 'OpDef') {
    icon = IconNames.JobProgramCode;
  }
  const Item = (
    <SmallRefBox
      iconName={icon}
      text={label}
      iconOnly={iconOnly}
      isDeleted={isDeleted}
    />
  );

  if (refTypeQuery.loading || isDeleted) {
    return Item;
  }
  return (
    <Link
      $variant="secondary"
      style={{
        width: '100%',
      }}
      to={peekingRouter.refUIUrl(rootTypeName, objRef, wfTable)}>
      {Item}
    </Link>
  );
};
