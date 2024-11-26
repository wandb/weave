/**
 * Handle loading call data for generic object comparison.
 */
import _ from 'lodash';
import React from 'react';

import {LoadingDots} from '../../../../LoadingDots';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {ComparePageObjectsLoaded} from './ComparePageObjectsLoaded';
import {Mode} from './types';

type ComparePageCallsProps = {
  entity: string;
  project: string;
  callIds: string[];
  mode: Mode;
  baselineEnabled: boolean;
  onlyChanged: boolean;
};

export const ComparePageCalls = ({
  entity,
  project,
  callIds,
  mode,
  baselineEnabled,
  onlyChanged,
}: ComparePageCallsProps) => {
  const {useCalls} = useWFHooks();
  const calls = useCalls(entity, project, {callIds});
  if (calls.loading) {
    return <LoadingDots />;
  }

  // The calls don't come back sorted in the same order as the callIds we provided
  const resultCalls = calls.result ?? [];
  const resultCallsIndex = _.keyBy(resultCalls, 'callId');
  const traceCalls = callIds
    .map(id => resultCallsIndex[id]?.traceCall)
    .filter((c): c is NonNullable<typeof c> => c != null);

  return (
    <ComparePageObjectsLoaded
      objectType="call"
      objects={traceCalls}
      objectIds={callIds}
      mode={mode}
      baselineEnabled={baselineEnabled}
      onlyChanged={onlyChanged}
    />
  );
};
