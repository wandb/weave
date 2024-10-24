import {
  ApolloClient,
  gql,
  TypedDocumentNode,
  useApolloClient,
} from '@apollo/client';
import {Box} from '@mui/material';
import {getTypeName, Type} from '@wandb/weave/core';
import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  ObjectRef,
  parseRef,
  refUri, WandbArtifactRef, WeaveObjectRef,
} from '@wandb/weave/react';
import React, {FC} from 'react';

import {hexToRGB, MOON_300} from '../../../../common/css/globals.styles';
import {Icon, IconName, IconNames} from '../../../Icon';
import {useWeaveflowRouteContext} from '../Browse3/context';
import {Link} from '../Browse3/pages/common/Links';
import {useWFHooks} from '../Browse3/pages/wfReactInterface/context';
import {
  ObjectVersionKey,
  OpVersionKey,
} from '../Browse3/pages/wfReactInterface/wfDataModelHooksInterface';

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

export const SmallArtifactRef: FC<{
  objRef: WandbArtifactRef;
  wfTable?: WFDBTableType;
  iconOnly?: boolean;
}> = ({objRef , wfTable, iconOnly = false}) => {
  const {
    useObjectVersion,
    derived: {useRefsType},
  } = useWFHooks();

  // TODO check if artifact present before creating possible link to it

  // let objVersionKey: ObjectVersionKey | null = null;

  // call out the use of this as a link back to model registry
  // objVersionKey = {
  //   scheme: 'wandb-artifact',
  //   entity: objRef.entityName,
  //   project: objRef.projectName,
  //   objectId: objRef.artifactName,
  //   versionHash: objRef.artifactVersion,
  //   path: objRef.artifactPath,
  //   refExtra: objRef.artifactRefExtra,
  // };

  // const apolloClient = useApolloClient();
  //
  // // VIEWER_QUERY for inspo
  // const ARTIFACT_BY_NAME_QUERY = gql`
  //   query ArtifactByName(
  //     $entityName: String!,
  //     $projectName: String!,
  //     $name: String!
  //   ) {
  //     project(name: $projectName, entityName: $entityName) {
  //       artifact(name: $name) {
  //         id
  //         name
  //         description
  //         createdAt
  //         updatedAt
  //         size
  //         state
  //       }
  //     }
  //   }
  // `;
  //
  // apolloClient.query({query: ARTIFACT_BY_NAME_QUERY as any}).then(result => {
  //   const info = result.data.viewer;
  // });

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
              flex: '0 0 22px',
              justifyContent: 'center',
              alignItems: 'center',
            }}>
          <Icon name={IconNames.OpenNewTab} width={14} height={14} />
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
                }}>
              {objRef.artifactName}:{objRef.artifactVersion}
            </Box>
        )}
      </Box>
  );

  return (
  <Link
      $variant="secondary"
          style={{
            width: '100%',
            minHeight: '38px',
          }}
      as="a"
      href={`${window.location.origin}/${objRef.entityName}/${objRef.projectName}/artifacts/model/${objRef.artifactName}/${objRef.artifactVersion}/overview`}
      target="_blank" rel="noopener noreferrer"
    >
    {Item}
  </Link>
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

  const objectVersion = useObjectVersion(objVersionKey);
  const opVersion = useOpVersion(opVersionKey);
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
          <Icon name={icon} width={14} height={14} />
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
                }}>
              {label}
            </Box>
        )}
      </Box>
  );
  if (refTypeQuery.loading) {
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
  const isArtifactRef = isWandbArtifactRef(objRef);
  const isWeaveObjRef = isWeaveObjectRef(objRef);

  if (!isArtifactRef && !isWeaveObjRef) {
    return <div>[Error: non wandb ref]</div>;
  }

  // There is now a dependency on the WandbArtifactRef type for the functionality of linking from weave to model artifacts
  if (isArtifactRef) {
    return <SmallArtifactRef objRef={objRef} />
  }
  return <SmallWeaveRef objRef={objRef}/>
};

export const parseRefMaybe = (s: string): ObjectRef | null => {
  try {
    return parseRef(s);
  } catch (e) {
    return null;
  }
};
