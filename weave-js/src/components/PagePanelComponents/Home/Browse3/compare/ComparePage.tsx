/**
 * Dispatch to call or object specific comparison based on query parameters.
 */

import React from 'react';
import {useHistory} from 'react-router-dom';

import {TargetBlank} from '../../../../../common/util/links';
import {Empty} from '../pages/common/Empty';
import {
  getParamArray,
  queryGetBoolean,
  queryGetDict,
  queryGetString,
} from '../urlQueryUtil';
import {ComparePageCalls} from './ComparePageCalls';
import {ComparePageObjects} from './ComparePageObjects';

type ComparePageProps = {
  entity: string;
  project: string;
};

export const ComparePage = ({entity, project}: ComparePageProps) => {
  const history = useHistory();
  const d = queryGetDict(history);
  const mode =
    queryGetString(history, 'mode') === 'unified' ? 'unified' : 'parallel';
  const baselineEnabled = queryGetBoolean(history, 'baseline', false);
  const onlyChanged = queryGetBoolean(history, 'changed', false);
  const callIds = getParamArray(d, 'call');

  if (callIds.length) {
    return (
      <ComparePageCalls
        entity={entity}
        project={project}
        callIds={callIds}
        mode={mode}
        baselineEnabled={baselineEnabled}
        onlyChanged={onlyChanged}
      />
    );
  }

  const objs = getParamArray(d, 'obj');
  if (objs.length) {
    return (
      <ComparePageObjects
        entity={entity}
        project={project}
        objectIds={objs}
        mode={mode}
        baselineEnabled={baselineEnabled}
        onlyChanged={onlyChanged}
      />
    );
  }

  // Currently nothing links to this state but query parameters
  // are sometimes dropped during dev reloading.
  return (
    <Empty
      icon="baseline-alt"
      heading="Compare objects or calls"
      description="This page allows you to compare objects or calls."
      moreInformation={
        <>
          Learn how to{' '}
          <TargetBlank href="http://wandb.me/weave_compare">
            compare versions
          </TargetBlank>{' '}
          in Weave.
        </>
      }
    />
  );
};
