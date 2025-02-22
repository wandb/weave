/**
 * Display a link to a Weave object.
 */

import React from 'react';

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
import {useWFHooks} from '../pages/wfReactInterface/context';
import {SmallRefLoaded} from './SmallRefLoaded';
import {WFDBTableType} from './types';

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
};

const getObjectVersionLabel = (
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
  wfTable?: WFDBTableType;
  iconOnly?: boolean;
  noLink?: boolean;
};

export const SmallWeaveRef = ({
  objRef,
  wfTable,
  iconOnly = false,
  noLink = false,
}: SmallWeaveRefProps) => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const {useObjectVersion} = useWFHooks();
  const objectVersion = useObjectVersion(
    {
      scheme: 'weave',
      entity: objRef.entityName,
      project: objRef.projectName,
      weaveKind: objRef.weaveKind,
      objectId: objRef.artifactName,
      versionHash: objRef.artifactVersion,
      path: '',
      refExtra: objRef.artifactRefExtra,
    },
    true
  );

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
  const url = peekingRouter.refUIUrl(rootTypeName, objRef, wfTable);
  const label = iconOnly
    ? undefined
    : getObjectVersionLabel(objRef, versionIndex);
  return (
    <TailwindContents>
      <SmallRefLoaded
        icon={icon}
        label={label}
        url={url}
        error={error}
        noLink={noLink}
      />
    </TailwindContents>
  );
};
