import {Box} from '@mui/material';
import * as Tooltip from '@radix-ui/react-tooltip';
import {useArtifactWeaveReference} from '@wandb/weave/common/hooks/useArtifactWeaveReference';
import {getTypeName, Type} from '@wandb/weave/core';
import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  ObjectRef,
  refUri,
  WandbArtifactRef,
  WeaveObjectRef,
} from '@wandb/weave/react';
import React, {FC} from 'react';

import {hexToRGB, MOON_300} from '../../../../../common/css/globals.styles';
import {Icon, IconName, IconNames} from '../../../../Icon';
import {fetchArtifactRefPageUrl} from '../artifactRegistry';
import {useWeaveflowRouteContext} from '../context';
import {Link} from '../pages/common/Links';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {isObjDeleteError} from '../pages/wfReactInterface/utilities';
import {
  ObjectVersionKey,
  OpVersionKey,
} from '../pages/wfReactInterface/wfDataModelHooksInterface';

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

export const SmallRefBox: FC<{
  iconName: IconName;
  text: string;
  iconOnly?: boolean;
  isDeleted?: boolean;
}> = ({iconName, text, iconOnly = false, isDeleted = false}) => (
  <Box display="flex" alignItems="center">
    <Box
      mr="4px"
      bgcolor={hexToRGB(MOON_300, 0.48)}
      sx={{
        height: '22px',
        width: '22px',
        borderRadius: '16px',
        display: 'flex',
        flex: '0 0 22px',
        justifyContent: 'center',
        alignItems: 'center',
      }}>
      <Icon name={iconName} width={14} height={14} />
    </Box>
    {!iconOnly && (
      <Box
        sx={{
          height: '22px',
          flex: 1,
          minWidth: 0,
          overflow: 'hidden',
          whiteSpace: 'nowrap',
          textOverflow: 'ellipsis',
          textDecoration: isDeleted ? 'line-through' : 'none',
        }}>
        {text}
      </Box>
    )}
  </Box>
);

export const SmallArtifactRef: FC<{
  objRef: WandbArtifactRef;
  iconOnly?: boolean;
}> = ({objRef}) => {
  const {loading, artInfo} = useArtifactWeaveReference({
    entityName: objRef.entityName,
    projectName: objRef.projectName,
    artifactName: objRef.artifactName + ':' + objRef.artifactVersion,
  });
  if (loading) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          minHeight: '38px',
          display: 'flex',
          alignItems: 'center',
        }}>
        <SmallRefBox iconName={IconNames.Loading} text="Loading..." />
      </Box>
    );
  }

  const artifactUrl = artInfo
    ? fetchArtifactRefPageUrl({
        entityName: objRef.entityName,
        projectName: objRef.projectName,
        artifactName: objRef.artifactName,
        artifactVersion: objRef.artifactVersion,
        artifactType: artInfo?.artifactType,
        orgName: artInfo?.orgName,
      })
    : null;

  const Content = (
    <Tooltip.Provider delayDuration={150} skipDelayDuration={50}>
      <Tooltip.Root>
        <Box
          sx={{
            width: '100%',
            height: '100%',
            minHeight: '38px',
            display: 'flex',
            alignItems: 'center',
            cursor: artifactUrl ? 'pointer' : 'not-allowed',
          }}>
          <Tooltip.Trigger asChild>
            <Box sx={{display: 'flex', alignItems: 'center'}}>
              <SmallRefBox
                iconName={IconNames.Registries}
                text={`${objRef.artifactName}:${objRef.artifactVersion}`}
              />
            </Box>
          </Tooltip.Trigger>
        </Box>
        <Tooltip.Portal>
          <Tooltip.Content
            side="top"
            sideOffset={8}
            className="rounded bg-moon-900 px-3 py-2 text-sm text-moon-200"
            style={{
              zIndex: 9999,
              position: 'relative',
              backgroundColor: '#1a1a1a',
              color: '#e0e0e0',
              padding: '8px 12px',
              borderRadius: '4px',
            }}>
            {artifactUrl
              ? objRef.artifactPath
              : 'No link detected for this wandb artifact reference: ' +
                objRef.artifactPath}
            <Tooltip.Arrow style={{fill: '#1a1a1a'}} />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );

  return artifactUrl ? (
    <Link
      $variant="secondary"
      style={{width: '100%', height: '100%'}}
      as="a"
      href={artifactUrl}>
      {Content}
    </Link>
  ) : (
    Content
  );
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

export const SmallRef: FC<{
  objRef: ObjectRef;
  wfTable?: WFDBTableType;
  iconOnly?: boolean;
}> = ({objRef, wfTable, iconOnly = false}) => {
  if (isWeaveObjectRef(objRef)) {
    return (
      <SmallWeaveRef objRef={objRef} wfTable={wfTable} iconOnly={iconOnly} />
    );
  }
  if (isWandbArtifactRef(objRef)) {
    return <SmallArtifactRef objRef={objRef} />;
  }
  return <div>[Error: non wandb ref]</div>;
};
