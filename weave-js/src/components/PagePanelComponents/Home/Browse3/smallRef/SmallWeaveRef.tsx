/**
 * Display a link to a Weave object.
 */

import React, {useMemo} from 'react';

import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  ObjectRef,
  WeaveObjectRef,
} from '../../../../../react';
import {IconName, IconNames} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {TailwindContents} from '../../../../Tailwind';
import {useWeaveflowRouteContext} from '../context';
import {Id} from '../pages/common/Id';
import {
  useCall,
  useObjectVersion,
  useRootObjectVersions,
} from '../pages/wfReactInterface/tsDataModelHooks';
import {KnownBaseObjectClassType} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallOpVersionsRef} from './SmallOpVersionsRef';
import {SmallRefLoaded} from './SmallRefLoaded';

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

// TODO: Unify with OBJECT_ICONS in ObjectVersionPage
const ICON_MAP: Record<string, IconName> = {
  ActionSpec: IconNames.RocketLaunch,
  AnnotationSpec: IconNames.ForumChatBubble,
  Dataset: IconNames.Table,
  Evaluation: IconNames.BaselineAlt,
  Leaderboard: IconNames.BenchmarkSquare,
  List: IconNames.List, // TODO: Not sure how you get this type
  Model: IconNames.Model,
  Op: IconNames.JobProgramCode,
  Prompt: IconNames.ForumChatBubble,
  Scorer: IconNames.TypeNumberAlt,
  Monitor: IconNames.JobAutomation,
};

export const getObjectVersionLabel = (
  objRef: ObjectRef,
  versionIndex: number
): string => {
  let label = objRef.artifactName + ':';
  if (versionIndex >= 0) {
    label += 'v' + versionIndex;
  } else {
    label += objRef.artifactVersion.slice(0, 6);
  }
  if (objRef.artifactRefExtra) {
    label += '/' + objRef.artifactRefExtra;
  }
  return label;
};

type SmallWeaveRefProps = {
  objRef: WeaveObjectRef;
  iconOnly?: boolean;
  noLink?: boolean;
};

export const SmallWeaveRef = ({
  objRef,
  iconOnly = false,
  noLink = false,
}: SmallWeaveRefProps) => {
  return (
    <TailwindContents>
      {objRef.artifactVersion === '*' ? (
        objRef.weaveKind === 'op' ? (
          <SmallOpVersionsRef objRef={objRef} />
        ) : (
          <SmallObjectVersionsRef
            objRef={objRef}
            iconOnly={iconOnly}
            noLink={noLink}
          />
        )
      ) : objRef.weaveKind === 'call' ? (
        <SmallWeaveCallRef
          objRef={objRef}
          iconOnly={iconOnly}
          noLink={noLink}
        />
      ) : (
        <SmallWeaveObjectRef
          objRef={objRef}
          iconOnly={iconOnly}
          noLink={noLink}
        />
      )}
    </TailwindContents>
  );
};

export const SmallWeaveObjectRef = ({
  objRef,
  iconOnly = false,
  noLink = false,
}: SmallWeaveRefProps) => {
  const {peekingRouter} = useWeaveflowRouteContext();

  const objectVersion = useObjectVersion({
    key: {
      scheme: 'weave',
      entity: objRef.entityName,
      project: objRef.projectName,
      weaveKind: objRef.weaveKind,
      objectId: objRef.artifactName,
      versionHash: objRef.artifactVersion,
      path: '',
      refExtra: objRef.artifactRefExtra,
    },
    metadataOnly: true,
  });

  const error = objectVersion?.error ?? null;
  if (objectVersion.loading && !error) {
    return <LoadingDots />;
  }

  // If the query for version number / object type fails,
  // we will render a generic object icon and digest.
  const objVersion = objectVersion.result ?? {
    baseObjectClass: undefined,
    versionIndex: -1,
  };
  const {baseObjectClass, versionIndex} = objVersion;
  const rootTypeName =
    objRef.weaveKind === 'op' ? 'Op' : baseObjectClass ?? 'Object';

  const icon = ICON_MAP[rootTypeName] ?? IconNames.CubeContainer;

  const url = peekingRouter.refUIUrl(
    rootTypeName,
    objRef,
    objRef.weaveKind === 'op' ? 'OpVersion' : undefined
  );
  const label = iconOnly
    ? undefined
    : getObjectVersionLabel(objRef, versionIndex);

  return (
    <SmallRefLoaded
      icon={icon}
      label={label}
      url={url}
      error={error}
      noLink={noLink}
    />
  );
};

export const SmallWeaveCallRef = ({
  objRef,
  iconOnly = false,
  noLink = false,
}: SmallWeaveRefProps) => {
  const {peekingRouter} = useWeaveflowRouteContext();

  const callKey = {
    entity: objRef.entityName,
    project: objRef.projectName,
    callId: objRef.artifactName,
  };

  const callResult = useCall({key: callKey});

  const error = callResult.loading
    ? null
    : callResult.result
    ? null
    : new Error('Call not found');

  if (callResult.loading) {
    return <LoadingDots />;
  }

  const icon = IconNames.LayoutTabs;
  const url = peekingRouter.callUIUrl(
    objRef.entityName,
    objRef.projectName,
    objRef.artifactName,
    objRef.artifactName
  );

  // For calls, we use the display name if available, otherwise the span name or call ID
  const callData = callResult.result;
  let label = undefined;

  if (!iconOnly) {
    if (callData) {
      label = callData.displayName || callData.spanName || objRef.artifactName;
    } else {
      label = objRef.artifactName;
    }
  }

  // Add an Id component as suffix
  const suffix = iconOnly ? null : <Id id={objRef.artifactName} type="Call" />;

  return (
    <SmallRefLoaded
      icon={icon}
      label={label}
      url={url}
      error={error}
      noLink={noLink}
      suffix={suffix}
    />
  );
};

export const SmallObjectVersionsRef = ({
  objRef,
  iconOnly,
  noLink,
}: SmallWeaveRefProps) => {
  const {peekingRouter} = useWeaveflowRouteContext();

  const objectVersions = useRootObjectVersions({
    entity: objRef.entityName,
    project: objRef.projectName,
    filter: {objectIds: [objRef.artifactName]},
  });

  const error =
    objectVersions?.error ??
    (objectVersions.result?.length === 0 ? new Error('Not found') : null);

  const objVersion = objectVersions.result?.[0] ?? {
    baseObjectClass: undefined,
    versionIndex: -1,
  };

  const baseObjectClass =
    objVersion.baseObjectClass as KnownBaseObjectClassType;

  const url = useMemo(
    () =>
      peekingRouter.objectVersionsUIUrl(objRef.entityName, objRef.projectName, {
        baseObjectClass,
        objectName: objRef.artifactName,
      }),
    [objRef, peekingRouter, baseObjectClass]
  );

  const rootTypeName = baseObjectClass ?? 'Object';

  const icon = ICON_MAP[rootTypeName] ?? IconNames.CubeContainer;

  return objectVersions.loading && !error ? (
    <LoadingDots />
  ) : (
    <TailwindContents>
      <SmallRefLoaded
        icon={icon}
        label={objRef.artifactName}
        url={url}
        error={error}
        noLink={noLink}
      />
    </TailwindContents>
  );
};
