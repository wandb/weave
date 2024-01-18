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

export const SmallRef: FC<{objRef: ArtifactRef; wfTable?: WFDBTableType}> = ({
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
  const label =
    objRef.artifactName +
    ':' +
    objRef.artifactVersion.slice(0, 6) +
    // Is this correct? Should we parse this in any special way?
    (objRef.artifactPath ? '/' + objRef.artifactPath : '');
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
      <Box mr={1} sx={{height: '1rem'}}>
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
    <Link to={peekingRouter.refUIUrl(rootTypeName, objRef, wfTable)}>
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
