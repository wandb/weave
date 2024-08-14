import React from 'react';

import {Loading} from '../../../../Loading';
import {Tailwind} from '../../../../Tailwind';
import {SimplePageLayout} from '../pages/common/SimplePageLayout';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {DiffHeaderCalls} from './DiffHeaderCalls';
import {ObjectDiffSelector} from './ObjectDiffSelector';

type DiffPageCallsProps = {
  entity: string;
  project: string;

  diffMode: string;
  setDiffMode: (mode: string) => void;

  calls: string[];
};

export const DiffPageCalls = ({
  entity,
  project,
  diffMode,
  setDiffMode,
  calls,
}: DiffPageCallsProps) => {
  const {useCall} = useWFHooks();

  console.log({calls});
  const callId = calls[0];
  const callId2 = calls[1] ?? callId;

  const call1 = useCall({
    entity,
    project,
    callId,
  });
  const call2 = useCall({
    entity,
    project,
    callId: callId2,
  });

  if (call1.loading || call2.loading) {
    return <Loading />;
  }
  const left = call1.result;
  const right = call2.result;
  return (
    <SimplePageLayout
      title="Compare calls"
      hideTabsIfSingle
      tabs={[
        {
          label: '',
          content: (
            <Tailwind style={{display: 'contents'}}>
              <DiffHeaderCalls calls={calls} left={callId} right={callId2} />
              <ObjectDiffSelector
                objectType="call"
                diffMode={diffMode}
                setDiffMode={setDiffMode}
                left={left}
                right={right}
              />
            </Tailwind>
          ),
        },
      ]}
    />
  );
};
