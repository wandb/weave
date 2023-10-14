import React, {FC, useMemo} from 'react';
import {Chip} from '@mui/material';
import {
  ArtifactRef,
  isWandbArtifactRef,
  parseRef,
  refUri,
  useNodeValue,
} from '@wandb/weave/react';
import {
  callOpVeryUnsafe,
  constString,
  getTypeName,
  Node,
  Type,
} from '@wandb/weave/core';
import {Dataset as DatasetIcon} from '@mui/icons-material';
import {CheckBoxOutlineBlank as CheckBoxOutlineBlankIcon} from '@mui/icons-material';
import {SmartToy as SmartToyIcon} from '@mui/icons-material';
import {TableRows as TableRowsIcon} from '@mui/icons-material';
import {DataObject as DataObjectIcon} from '@mui/icons-material';
import {Link} from './CommonLib';
import {URL_BROWSE2} from '@wandb/weave/urls';
import {Box, Typography} from '@material-ui/core';

const getRootType = (t: Type): Type => {
  if (
    (t as any)._base_type != null &&
    (t as any)._base_type?.type !== 'Object'
  ) {
    return getRootType((t as any)._base_type);
  }
  return t;
};

const refUIUrl = (rootTypeName: string, objRef: ArtifactRef) => {
  if (!isWandbArtifactRef(objRef)) {
    throw new Error('Not a wandb artifact ref');
  }
  return `/${URL_BROWSE2}/${objRef.entityName}/${objRef.projectName}/${rootTypeName}/${objRef.artifactName}/${objRef.artifactVersion}`;
};

export const SmallRef: FC<{objRef: ArtifactRef}> = ({objRef}) => {
  const refTypeNode = useMemo(() => {
    const refNode = callOpVeryUnsafe('ref', {uri: constString(refUri(objRef))});
    return callOpVeryUnsafe('Ref-type', {ref: refNode}) as Node;
  }, [objRef]);
  const refTypeQuery = useNodeValue(refTypeNode);
  const refType: Type = refTypeQuery.result ?? 'unknown';
  const rootType = getRootType(refType);
  const label = objRef.artifactName + ':' + objRef.artifactVersion.slice(0, 6);
  const rootTypeName = getTypeName(rootType);
  let icon = <CheckBoxOutlineBlankIcon />;
  if (rootTypeName === 'Dataset') {
    icon = <DatasetIcon />;
  } else if (rootTypeName === 'Model') {
    icon = <SmartToyIcon />;
  } else if (rootTypeName === 'list') {
    icon = <TableRowsIcon />;
  } else if (rootTypeName === 'OpDef') {
    icon = <DataObjectIcon />;
  }
  let Item = (
    <Box display="flex" alignItems="center">
      <Box mr={1}>{icon}</Box>
      <Typography variant="body1">{label}</Typography>
    </Box>
  );
  if (refTypeQuery.loading) {
    return Item;
  }
  return <Link to={refUIUrl(rootTypeName, objRef)}>{Item}</Link>;
};

export const parseRefMaybe = (s: string): ArtifactRef | null => {
  try {
    return parseRef(s);
  } catch (e) {}
  return null;
};
