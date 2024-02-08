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

import {hexToRGB, MOON_300} from '../../../../common/css/globals.styles';
import {Icon, IconName, IconNames} from '../../../Icon';
import {useWeaveflowRouteContext} from '../Browse3/context';
import {Link} from '../Browse3/pages/common/Links';

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
  let label = `${objRef.artifactName}:${objRef.artifactVersion.slice(0, 6)}`;
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
  const {label} = objectRefDisplayName(objRef);

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
    <Box display="flex" alignItems="center">
      <Box
        mr="4px"
        bgcolor={hexToRGB(MOON_300, 0.48)}
        sx={{
          height: '22px',
          width: '22px',
          borderRadius: '16px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}>
        <Icon name={icon} width={14} height={14} />
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
      $variant="secondary"
      to={peekingRouter.refUIUrl(rootTypeName, objRef, wfTable)}>
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
