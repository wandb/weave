/**
 * Display a link to a Weave object.
 */

import React from 'react';

import {ObjectRef, WeaveObjectRef} from '../../../../react';
import {IconName, IconNames} from '../../../Icon';
import {LoadingDots} from '../../../LoadingDots';
import {TailwindContents} from '../../../Tailwind';
import {useWeaveflowRouteContext, WFDBTableType} from './context';
import {useWFHooks} from './pages/wfReactInterface/context';
import {SmallRefLoaded} from './SmallRefLoaded';

type SmallRefObjectProps = {
  objRef: WeaveObjectRef;
  wfTable?: WFDBTableType;
  iconOnly?: boolean;
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

export const SmallRefObject = ({
  objRef,
  wfTable,
  iconOnly = false,
}: SmallRefObjectProps) => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const {useObjectVersion} = useWFHooks();
  // TODO: Could we add support for a metadata_only query?
  const objectVersion = useObjectVersion({
    scheme: 'weave',
    entity: objRef.entityName,
    project: objRef.projectName,
    weaveKind: objRef.weaveKind,
    objectId: objRef.artifactName,
    versionHash: objRef.artifactVersion,
    path: '',
    refExtra: objRef.artifactRefExtra,
  });

  if (objectVersion.loading) {
    // TODO: Is this loading indicator what we want?
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
      <SmallRefLoaded icon={icon} label={label} url={url} />
    </TailwindContents>
  );
};
