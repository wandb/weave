import {Dataset as DatasetIcon} from '@mui/icons-material';
import {SmartToy as SmartToyIcon} from '@mui/icons-material';
import {TableRows as TableRowsIcon} from '@mui/icons-material';
import {DataObject as DataObjectIcon} from '@mui/icons-material';
import {Spoke as SpokeIcon} from '@mui/icons-material';
import {Box} from '@mui/material';
import {
  callOpVeryUnsafe,
  constString,
  getTypeName,
  Node,
  Type,
} from '@wandb/weave/core';
import {
  ArtifactRef,
  isWandbArtifactRef,
  ObjectRef,
  parseRef,
  refUri,
  useNodeValue,
} from '@wandb/weave/react';
import React, {FC, useMemo} from 'react';

import {useWeaveflowRouteContext} from '../Browse3/context';
import {Link} from './CommonLib';

const getRootType = (t: Type): Type => {
  if (
    (t as any)._base_type != null &&
    (t as any)._base_type?.type !== 'Object'
  ) {
    return getRootType((t as any)._base_type);
  }
  return t;
};

type WFDBTableType =
  | 'Op'
  | 'OpVersion'
  | 'Type'
  | 'TypeVersion'
  | 'Trace'
  | 'Call'
  | 'Object'
  | 'ObjectVersion';

export const objectRefDisplayName = (objRef: ObjectRef) => {
  let label = objRef.artifactName + ':' + objRef.artifactVersion.slice(0, 6);
  let linkSuffix = '';

  // TEMP HACK (Tim): This is a temporary hack to ensure that SmallRef renders
  // the Evaluation rows with the correct label and link. There is a more full
  // featured solution here: https://github.com/wandb/weave/pull/1080 that needs
  // to be finished asap. This is just to fix the demo / first internal release.
  if (objRef.artifactPath.endsWith('rows%2F0')) {
    // decodeURIComponent is needed because the path is url encoded
    const artPath = decodeURIComponent(objRef.artifactPath);
    const parts = artPath.split('/');
    const firstParts = parts.slice(0, parts.length - 2);
    firstParts.push('rows');
    const labelPath = '/' + firstParts.join('/');
    label +=
      labelPath + (objRef.objectRefExtra ? '/' + objRef.objectRefExtra : '');

    linkSuffix =
      labelPath +
      (objRef.objectRefExtra ? '/index/' + objRef.objectRefExtra : '');
  }
  return {label, linkSuffix};
};
export const SmallRef: FC<{objRef: ObjectRef; wfTable?: WFDBTableType}> = ({
  objRef,
  wfTable,
}) => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const refTypeNode = useMemo(() => {
    const refNode = callOpVeryUnsafe('ref', {uri: constString(refUri(objRef))});
    return callOpVeryUnsafe('Ref-type', {ref: refNode}) as Node;
  }, [objRef]);

  const refTypeQuery = useNodeValue(refTypeNode);
  const refType: Type = refTypeQuery.result ?? 'unknown';
  const rootType = getRootType(refType);
  const {label, linkSuffix} = objectRefDisplayName(objRef);

  const rootTypeName = getTypeName(rootType);
  let icon = <SpokeIcon sx={{height: '100%'}} />;
  if (rootTypeName === 'Dataset') {
    icon = <DatasetIcon sx={{height: '100%'}} />;
  } else if (rootTypeName === 'Model') {
    icon = <SmartToyIcon sx={{height: '100%'}} />;
  } else if (rootTypeName === 'list') {
    icon = <TableRowsIcon sx={{height: '100%'}} />;
  } else if (rootTypeName === 'OpDef') {
    icon = <DataObjectIcon sx={{height: '100%'}} />;
  }
  const Item = (
    <Box display="flex" alignItems="center">
      <Box mr={1} sx={{height: '1rem', lineHeight: '20px'}}>
        {icon}
      </Box>
      {label}
    </Box>
  );
  if (refTypeQuery.loading) {
    return Item;
  }
  if (!isWandbArtifactRef(objRef)) {
    return <div>[Error: non wandb ref]</div>;
  }
  return (
    <Link
      to={peekingRouter.refUIUrl(rootTypeName, objRef, wfTable) + linkSuffix}>
      {Item}
    </Link>
  );
};

export const parseRefMaybe = (s: string): ArtifactRef | null => {
  try {
    return parseRef(s);
  } catch (e) {
    return null;
  }
};
