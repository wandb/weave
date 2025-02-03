import React from 'react';

import {parseRef} from '../../../../../../react';
import {LoadingDots} from '../../../../../LoadingDots';
import {useWFHooks} from '../wfReactInterface/context';
import {OpVersionKey} from '../wfReactInterface/wfDataModelHooksInterface';

type OpVersionIndexTextProps = {
  opVersionRef: string;
};

export const OpVersionIndexText = ({opVersionRef}: OpVersionIndexTextProps) => {
  const {useOpVersion} = useWFHooks();
  const ref = parseRef(opVersionRef);
  let opVersionKey: OpVersionKey | null = null;
  if ('weaveKind' in ref && ref.weaveKind === 'op') {
    opVersionKey = {
      entity: ref.entityName,
      project: ref.projectName,
      opId: ref.artifactName,
      versionHash: ref.artifactVersion,
    };
  }
  const opVersion = useOpVersion(opVersionKey);
  if (opVersion.loading) {
    return <LoadingDots />;
  }
  return opVersion.result ? (
    <span>v{opVersion.result.versionIndex}</span>
  ) : null;
};
